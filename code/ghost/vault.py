"""Encrypted-at-rest NVIDIA key vault under the gitignored .ghost/ (threat T1). Stdlib only; `cryptography` optional.

Windows: DPAPI via ctypes (per-user, no master key). Elsewhere: Fernet with a 0600 .ghost/master.key if `cryptography`
imports; otherwise available() is False. No function except get_secret() returns secret material, and get_secret() is
for ghost.llm only. Plaintext never touches disk; ciphertext is overwritten before an entry is dropped.
"""
import base64
import json
import os
import re
import sys
import threading
import uuid
from datetime import datetime, timezone

from .contract import REPO

DIR = REPO / ".ghost"
KEY_RX = re.compile(r"^nvapi-[A-Za-z0-9_-]{20,}$")
ROLES = ("default", "embed", "embed_large", "rerank", "parse", "chat")
_LOCK = threading.Lock()
_loaded: set[str] = set()  # plaintexts decrypted in this process, for log redaction only


class VaultUnavailable(RuntimeError):
    pass


# ---------------------------------------------------------------- crypto backends

def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    src, out = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), Blob()
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)):
        raise VaultUnavailable("DPAPI call failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def _fernet():
    from cryptography.fernet import Fernet
    DIR.mkdir(exist_ok=True)
    f = DIR / "master.key"
    if not f.exists():
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as h:
            h.write(Fernet.generate_key())
    return Fernet(f.read_bytes())


def storage_kind() -> str | None:
    if sys.platform == "win32":
        return "dpapi"
    try:
        import cryptography.fernet  # noqa: F401
        return "fernet"
    except ImportError:
        return None


def available() -> bool:
    return storage_kind() is not None


def _enc(value: str) -> str:
    raw = value.encode()
    blob = _dpapi(raw, True) if storage_kind() == "dpapi" else _fernet().encrypt(raw)
    return base64.b64encode(blob).decode()


def _dec(ct: str) -> str:
    blob = base64.b64decode(ct)
    return (_dpapi(blob, False) if storage_kind() == "dpapi" else _fernet().decrypt(blob)).decode()


# ---------------------------------------------------------------- files

def _write(name: str, obj) -> None:
    DIR.mkdir(exist_ok=True)
    tmp = DIR / f"{name}.{uuid.uuid4().hex}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(obj, h, indent=1)
    os.replace(tmp, DIR / name)


def _read(name: str, default):
    try:
        return json.loads((DIR / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _entries() -> list[dict]:
    return _read("vault.json", [])


def settings() -> dict:
    s = _read("settings.json", {})
    return {"active": s.get("active") if isinstance(s.get("active"), dict) else {},
            "models": s.get("models") if isinstance(s.get("models"), dict) else {}}


def _save_settings(s: dict) -> None:
    _write("settings.json", s)


def model_overrides() -> dict:
    return settings()["models"]


# ---------------------------------------------------------------- public API

def add(label: str, value: str, roles: list[str]) -> str:
    if not available():
        raise VaultUnavailable("no encryption backend; put the key in .env instead")
    if not isinstance(label, str) or not 1 <= len(label) <= 40:
        raise ValueError("label must be 1..40 characters")
    if not isinstance(value, str) or not KEY_RX.match(value):
        raise ValueError("invalid key format")
    roles = sorted(set(roles or ["default"]))
    if not set(roles) <= set(ROLES):
        raise ValueError("unknown role")
    ref = str(uuid.uuid4())
    entry = {"ref": ref, "label": label, "roles": roles, "preview": "nvapi-…" + value[-4:],
             "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ciphertext": _enc(value),
             "storage": storage_kind()}
    with _LOCK:
        _write("vault.json", _entries() + [entry])
    return ref


def list_entries() -> list[dict]:
    return [{k: v for k, v in e.items() if k != "ciphertext"} for e in _entries()]


def get_secret(ref: str) -> str:
    for e in _entries():
        if e["ref"] == ref:
            value = _dec(e["ciphertext"])
            _loaded.add(value)
            return value
    raise KeyError(ref)


def known_secrets() -> set[str]:
    return set(_loaded)


def delete(ref: str) -> None:
    with _LOCK:
        es = _entries()
        hit = next((e for e in es if e["ref"] == ref), None)
        if hit is None:
            raise KeyError(ref)
        hit["ciphertext"] = base64.b64encode(os.urandom(len(hit["ciphertext"]))).decode()  # overwrite first
        _write("vault.json", es)
        _write("vault.json", [e for e in es if e["ref"] != ref])
        s = settings()
        s["active"] = {r: v for r, v in s["active"].items() if v != ref}
        _save_settings(s)


def set_active(role: str, ref: str | None) -> None:
    if role not in ROLES:
        raise ValueError("unknown role")
    if ref is not None and not any(e["ref"] == ref for e in _entries()):
        raise KeyError(ref)
    with _LOCK:
        s = settings()
        if ref is None:
            s["active"].pop(role, None)
        else:
            s["active"][role] = ref
        _save_settings(s)


def active() -> dict:
    return settings()["active"]


def set_model(role: str, name: str) -> None:
    with _LOCK:
        s = settings()
        s["models"][role] = name
        _save_settings(s)


def record_test(ref: str, result: dict) -> None:
    with _LOCK:
        es = _entries()
        for e in es:
            if e["ref"] == ref:
                e["last_test"] = {"ok": bool(result.get("ok")), "latency_ms": result.get("latency_ms"),
                                  "model": result.get("model"),
                                  "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                _write("vault.json", es)
                return
