"""Confinement for untrusted inputs (architecture.md §7): paths, SQL dumps, PII in trails."""
import re
import sqlite3
from pathlib import Path

from .contract import DATASET

MAX_FILE_BYTES = 50 * 1024 * 1024
SQL_MAX_STEPS = 200_000_000  # VM instructions per dump; real snapshots use far fewer
ALLOWED_PRAGMAS = {"foreign_keys"}


class UnsafeInput(ValueError):
    pass


def safe_evidence_path(manifest_path: str) -> Path:
    """Resolve a manifest file_path (relative to dataset/) and confine it to dataset/evidence (T5, T6)."""
    base = (DATASET / "evidence").resolve()
    p = (DATASET / manifest_path).resolve()
    if not p.is_relative_to(base):
        raise UnsafeInput(f"path escapes evidence dir: {manifest_path!r}")
    if not p.is_file():
        raise UnsafeInput(f"not a file: {manifest_path!r}")
    if p.stat().st_size > MAX_FILE_BYTES:
        raise UnsafeInput(f"file over {MAX_FILE_BYTES} bytes: {manifest_path!r}")
    return p


def _authorizer(action, arg1, arg2, _db, _trigger):
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA and arg1 not in ALLOWED_PRAGMAS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and arg2 == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def open_sandboxed_sqlite(sql_text: str) -> sqlite3.Connection:
    """Load an untrusted SQL dump into an in-memory DB that cannot touch the filesystem (T4)."""
    if re.search(r"\bVACUUM\b", sql_text, re.I):  # VACUUM INTO writes a file and bypasses the authorizer
        raise sqlite3.DatabaseError("VACUUM not allowed in evidence dumps")
    conn = sqlite3.connect(":memory:")
    conn.set_authorizer(_authorizer)
    steps = [0]

    def budget():
        steps[0] += 1000
        return steps[0] > SQL_MAX_STEPS

    conn.set_progress_handler(budget, 1000)
    try:
        conn.executescript(sql_text)
    except sqlite3.DatabaseError:
        conn.close()
        raise
    conn.set_progress_handler(None, 0)
    return conn


_EMAIL = re.compile(r"([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_PHONE = re.compile(r"\+\d[\d ()\-]{6,}\d")  # all 1,034 dataset phones start with "+"; dates don't
_HASH = re.compile(r"\b([0-9a-f]{6})[0-9a-f]{58}\b")


def mask(value: str) -> str:
    """Mask one identifier for human-readable output. Resource ids pass through."""
    if _EMAIL.fullmatch(value):
        return _EMAIL.sub(r"\1***@\2", value)
    if _HASH.fullmatch(value):
        return value[:6] + "…"
    if _PHONE.fullmatch(value):
        return "***" + re.sub(r"\D", "", value)[-2:]
    return value


def mask_text(text: str) -> str:
    """Scrub emails, phone numbers and sha256 hashes out of free text (T9)."""
    text = _EMAIL.sub(r"\1***@\2", text)
    text = _HASH.sub(r"\1…", text)
    return _PHONE.sub(lambda m: "***" + re.sub(r"\D", "", m.group())[-2:], text)
