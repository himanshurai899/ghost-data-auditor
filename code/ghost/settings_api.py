"""Settings endpoints (docs/ui_redesign.md "Settings"): key vault, model overrides, catalog, connection test.

Keys are never returned, logged, or put in messages. Token/Host/Origin/body-size checks live in api.py middleware.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import deque
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import llm, vault

UUID_RX = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
MODEL_RX = r"^[A-Za-z0-9._/-]+$"
LLM_ROLES = tuple(llm.DEFAULT_MODELS)
CHAT_ROLES = ("fast", "reason", "vision", "guard")
TEST_LIMIT, TEST_WINDOW_S = 12, 60.0
_tests: deque = deque()
_catalog: dict = {"at": 0.0, "models": [], "note": ""}


class KeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=20, max_length=200)
    roles: list[str] = Field(default_factory=lambda: ["default"], max_length=len(vault.ROLES))


class ActiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(max_length=20)
    ref: Optional[str] = Field(default=None, max_length=36, pattern=UUID_RX)


class ModelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(max_length=20)
    model: str = Field(min_length=3, max_length=80, pattern=MODEL_RX)


class TestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: Optional[str] = Field(default=None, max_length=36, pattern=UUID_RX)
    role: str = Field(max_length=20)


def _http(url: str, headers: dict, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    if body is not None:
        return llm.urllib_transport(url, headers, body, timeout)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except OSError as e:
        raise TimeoutError(type(e).__name__) from None


def _message(status: int | None) -> str:
    return {200: "accepted", None: "timeout", 429: "rate limited (429)"}.get(status, f"rejected ({status})")


def _run_test(secret: str, role: str) -> dict:
    name = llm.model(role)
    auth = {"Authorization": f"Bearer {secret}", "Accept": "application/json"}
    js = {**auth, "Content-Type": "application/json"}
    if role in ("embed", "embed_large"):
        url, body = f"{llm.base_url()}/embeddings", {"input": ["ping"], "model": name, "input_type": "query",
                                                     "encoding_format": "float", "truncate": "END"}
    elif role in CHAT_ROLES:
        url, body = f"{llm.base_url()}/chat/completions", {"model": name, "max_tokens": 1, "temperature": 0,
                                                           "messages": [{"role": "user", "content": "ping"}],
                                                           "chat_template_kwargs": {"enable_thinking": False}}
    elif role == "rerank":
        url, body = f"{llm.retrieval_url()}/{name}/reranking", {"model": name, "query": {"text": "ping"},
                                                                "passages": [{"text": "ping"}], "truncate": "END"}
    else:  # parse needs an image: authenticated model-list check instead
        url, body = f"{llm.base_url()}/models", None
    t0 = time.monotonic()
    try:
        status, _ = _http(url, js if body is not None else auth, None if body is None else json.dumps(body).encode(), 10)
    except TimeoutError:
        status = None
    return {"ok": status == 200, "status": status, "latency_ms": int((time.monotonic() - t0) * 1000), "model": name,
            "message": _message(status)}


def register(app, deps):
    scrub = deps.scrub
    llm.load_env()  # .env keys are then visible to the env-key test; _redact covers every NVIDIA_API_KEY* value

    def _ref(ref: str | None) -> str | None:
        if ref is not None and not any(e["ref"] == ref for e in vault.list_entries()):
            raise HTTPException(404, "unknown key reference")
        return ref

    @app.get("/api/settings")
    def get_settings():
        s = vault.settings()
        env = {r.upper(): bool(os.environ.get(f"NVIDIA_API_KEY_{r.upper()}") or os.environ.get("NVIDIA_API_KEY"))
               for r in vault.ROLES}
        return scrub({"keys": vault.list_entries(), "active": s["active"], "models": llm.models(),
                      "base_url": llm.base_url(), "retrieval_url": llm.retrieval_url(), "env_keys": env,
                      "vault_available": vault.available()})

    @app.post("/api/settings/keys")
    def add_key(body: KeyIn):
        if not vault.available():
            raise HTTPException(501, "No encryption backend (install `cryptography`, or use Windows DPAPI). "
                                     "Put the key in .env as NVIDIA_API_KEY instead.")
        if not vault.KEY_RX.match(body.value):
            raise HTTPException(422, "key must look like nvapi-...")
        try:
            return {"ref": vault.add(body.label, body.value, body.roles)}
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        except vault.VaultUnavailable:
            raise HTTPException(501, "Key vault unavailable; use .env") from None

    @app.delete("/api/settings/keys/{ref}")
    def delete_key(ref: str):
        if not re.match(UUID_RX, ref):
            raise HTTPException(422, "ref must be a UUID")
        try:
            vault.delete(ref)
        except KeyError:
            raise HTTPException(404, "unknown key reference") from None
        return {"ok": True}

    @app.put("/api/settings/active")
    def put_active(body: ActiveIn):
        if body.role not in vault.ROLES:
            raise HTTPException(422, "unknown role")
        vault.set_active(body.role, _ref(body.ref))
        return {"ok": True}

    @app.put("/api/settings/models")
    def put_models(body: ModelIn):
        if body.role not in LLM_ROLES:
            raise HTTPException(422, "unknown role")
        vault.set_model(body.role, body.model)
        return {"ok": True}

    @app.get("/api/settings/catalog")
    def catalog():
        if time.time() - _catalog["at"] > 600:
            try:
                status, raw = _http(f"{llm.base_url()}/models", {"Accept": "application/json"}, None, 5)
                data = json.loads(raw)["data"] if status == 200 else []
                _catalog.update(models=[{"id": str(m["id"])[:120], "owned_by": str(m.get("owned_by", ""))[:60]}
                                        for m in data if isinstance(m, dict) and "id" in m],
                                note="" if status == 200 else "catalog unavailable")
            except (TimeoutError, ValueError, KeyError, TypeError):
                _catalog.update(models=[], note="catalog unavailable")
            _catalog["at"] = time.time()
        return scrub({"models": _catalog["models"], "note": _catalog["note"]})

    @app.post("/api/settings/test")
    def test(body: TestIn):
        if body.role not in LLM_ROLES:
            raise HTTPException(422, "unknown role")
        _ref(body.ref)
        now = time.monotonic()
        while _tests and now - _tests[0] > TEST_WINDOW_S:
            _tests.popleft()
        if len(_tests) >= TEST_LIMIT:
            raise HTTPException(429, "too many connection tests; wait a minute")
        _tests.append(now)
        try:
            secret = vault.get_secret(body.ref) if body.ref else llm.api_key(body.role)
        except Exception:
            return {"ok": False, "status": None, "latency_ms": 0, "model": llm.model(body.role), "message": "no key available"}
        result = _run_test(secret, body.role)
        if body.ref:
            vault.record_test(body.ref, result)
        return scrub(result)
