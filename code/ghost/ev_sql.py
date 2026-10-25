"""SQL snapshot exports (24): docs/evidence_field_map.md §2.1. Run via safety.open_sandboxed_sqlite."""
import json
import re
import sqlite3
from pathlib import Path

from .safety import open_sandboxed_sqlite

# collection -> (data_category, default system). Typed tables map onto the same collections as the
# generic record_json replicas, so one record handler serves both.
COLLECTIONS = {
    "customer_profiles": ("USER_PROFILE", "account_service"),
    "customer_search_documents": ("SEARCH_INDEX_ENTRY", "search_service"),
    "customer_analytics_reports": ("ANALYTICS_PROFILE", "analytics_platform"),
    "support_conversations": ("SUPPORT_MESSAGE", "support_platform"),
    "ticket_attachments": ("SUPPORT_ATTACHMENT", "support_platform"),
    "customer_export_jobs": ("USER_EXPORT", "export_service"),
    "connector_configurations": ("DATA_FLOW", "integration_service"),
    "backup_catalog": ("BACKUP_ARCHIVE", "backup_service"),
    "deleted_customer_references": ("ACCOUNT_TOMBSTONE", "identity_service"),
    "security_audit_events": ("SECURITY_AUDIT_LOG", "security_service"),
    "retained_order_records": ("LEGAL_HOLD_RECORD", "legal_service"),
}
# typed table -> collection. Inventory tables are covered by snapshot_scope; the rest by being the whole table.
INVENTORY = {
    "customer_profiles": "customer_profiles", "customer_search_documents": "customer_search_documents",
    "customer_analytics_profiles": "customer_analytics_reports", "support_records": "support_conversations",
    "customer_exports": "customer_export_jobs", "connector_subscriptions": "connector_configurations",
    "backup_restore_entries": "backup_catalog", "security_audit_records": "security_audit_events",
}
STANDALONE = {  # (accounts failover, search primary)
    "customer_profiles_primary": "customer_profiles", "customer_profiles_failover_replica": "customer_profiles",
    "search_documents_primary": "customer_search_documents",
}
TIME_COLUMNS = ("updated_at", "indexed_at")
# direct identifiers that must be gone from a REDACT/ANONYMIZE record (a stable user_N reference is not PII,
# except on analytics rows, where anonymization also unlinks it)
PII_KEYS = {"SUPPORT_MESSAGE": {"email", "phone", "email_hash", "name"},
            "ACCOUNT_TOMBSTONE": {"email", "phone", "email_hash", "name"},
            "ANALYTICS_PROFILE": {"email", "phone", "email_hash", "user_id"}}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _ref_keys(value, is_null):
    """customer_reference / subject_reference / uploaded_by ...: one of user_N, an email, or a sha256."""
    if is_null(value):
        return {}
    v = str(value).strip()
    if re.fullmatch(r"user_\d+", v):
        return {"user_id": v}
    if "@" in v:
        return {"email": v}
    if re.fullmatch(r"[0-9A-Fa-f]{64}", v):
        return {"email_hash": v}
    return {}


def _flag(value) -> bool:
    v = str(value).strip().lower()
    if v in ("1", "true"):
        return True
    if v in ("0", "false"):
        return False
    raise ValueError(f"not a boolean flag: {value!r}")


def _gather(r: dict, is_null) -> dict:
    """Pull the identifier fields of any record shape into one raw dict for norm_keys (first populated wins)."""
    r = {**r, **r["document"]} if isinstance(r.get("document"), dict) else r
    raw = {}

    def put(k, v):
        if not is_null(v) and k not in raw:
            raw[k] = v

    for k, fields in (("email", ("email", "owner_email", "customer_email", "requester_email")),
                      ("name", ("full_name", "name", "display_name", "requester_name")),
                      ("phone", ("phone", "owner_phone", "requester_phone")),
                      ("email_hash", ("email_hash",)), ("user_id", ("user_id",))):
        for f in fields:
            put(k, r.get(f))
    for f in ("customer_reference", "subject_reference", "subject_selector", "uploaded_by"):
        for k, v in _ref_keys(r.get(f), is_null).items():
            put(k, v)
    for f in ("message_text", "message_excerpt"):  # free text can carry an email
        m = _EMAIL.search(str(r.get(f) or ""))
        if m:
            put("email", m.group())
    return raw


def _classify(collection: str, r: dict, norm_keys, is_null):
    category = COLLECTIONS[collection][0]
    keys = norm_keys(_gather(r, is_null))
    present = {k for k, _ in keys}
    pii = frozenset(present & PII_KEYS.get(category, set()))
    if category == "DATA_FLOW":
        obs = "FLOW_ACTIVE" if _flag(r["enabled"]) else "FLOW_DISABLED"
    elif category == "BACKUP_ARCHIVE":
        obs = "RESTORE_OPEN" if _flag(r["restore_allowed"]) else "RESTORE_BLOCKED"
    elif category == "ANALYTICS_PROFILE":
        obs = "PRESENT" if pii else "ANONYMIZED"
    elif category in ("SUPPORT_MESSAGE", "ACCOUNT_TOMBSTONE"):
        obs = "PRESENT" if pii else "REDACTED"
    else:
        obs = "PRESENT"
    return category, obs, keys, pii


def parse(path: Path, meta: dict) -> tuple[list, list]:
    """-> (facts: list[evidence.Fact], coverage: list[evidence.Coverage]). Raise on malformed input."""
    from .evidence import Coverage, Fact, is_null, norm_keys, system_for  # evidence imports this module

    text = path.read_text(encoding="utf-8")
    conn = open_sandboxed_sqlite(text)
    conn.row_factory = sqlite3.Row
    m = re.search(r"^-- Captured at: (\S+)", text, re.M) or re.search(r"^-- snapshot_completed_at=(\S+)", text, re.M)
    snap = m.group(1) if m else meta["captured_at"]
    tables = sorted(r[0] for r in conn.execute("select name from sqlite_master where type='table'"))
    scope = {}
    if "snapshot_scope" in tables:
        scope = {r["origin_system"]: r["captured_at"] for r in conn.execute("select * from snapshot_scope")}

    facts, data_rows = [], 0
    cov_systems = {}  # system -> observed_at

    def emit(collection, rid, explicit, record, row_time, table_time):
        category, obs, keys, pii = _classify(collection, record, norm_keys, is_null)
        system = system_for(rid, explicit) or COLLECTIONS[collection][1]
        facts.append(Fact(meta["file_id"], "FILE", meta["captured_at"],
                          row_time if not is_null(row_time) else scope.get(system) or table_time,
                          system, rid, category, obs, keys, pii))
        return system

    for t in tables:
        if t == "snapshot_scope":
            continue
        rows = [dict(r) for r in conn.execute(f"select * from {t} order by resource_id")]
        data_rows += len(rows)
        if t in INVENTORY or t in STANDALONE:
            collection = INVENTORY.get(t) or STANDALONE[t]
            tcol = next((c for c in TIME_COLUMNS if rows and c in rows[0]), None) if rows else None
            for r in rows:
                emit(collection, r["resource_id"], None, r, r.get(tcol) if tcol else None, snap)
            system = COLLECTIONS[collection][1]
            if t in INVENTORY:
                if system in scope:  # snapshot_scope says this system's table is complete, even when empty
                    cov_systems[system] = scope[system]
            else:
                cov_systems[system] = snap
        elif t.startswith("customer_data_"):
            for r in rows:
                if r["collection_name"] not in COLLECTIONS:
                    raise ValueError(f"unknown collection {r['collection_name']!r} in {t}")
                s = emit(r["collection_name"], r["resource_id"], r["origin_system"], json.loads(r["record_json"]),
                         r["updated_at"], snap)
                if t == "customer_data_primary":  # replica-only rows are drift, not coverage
                    cov_systems[s] = snap
        else:
            raise ValueError(f"unknown table {t!r}")
    conn.close()
    if not data_rows:  # a file with no data rows proves nothing (F-012)
        return [], []
    facts = sorted(dict.fromkeys(facts), key=lambda f: (f.evidence_id, f.system_id, f.resource_id, f.observation))
    coverage = [Coverage(meta["file_id"], s, meta["captured_at"], o) for s, o in sorted(cov_systems.items())]
    return facts, coverage
