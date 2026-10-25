"""JSON evidence (28): docs/evidence_field_map.md §2.2 and §2.5 ledger rows.

Shapes: snapshot bundle {snapshots:[{captured_at,data_store,collection,records}]}, service_resource_export
{service_exports:{system:{list:[...]}}}, flat {records:[...]} (ledger files and the analytics / export-job files).
"""
import json
import re
from pathlib import Path

LEDGER = "operational_record_history"
LEDGER_STATE = {"FOUND": "PRESENT", "NOT_FOUND": "ABSENT", "IDENTIFIABLE": "PRESENT", "ANONYMIZED": "ANONYMIZED",
                "REDACTED": "REDACTED", "DISABLED": "FLOW_DISABLED", "BLOCKED": "RESTORE_BLOCKED"}
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+")
HEX64 = re.compile(r"[0-9a-fA-F]{64}")
USER = re.compile(r"user_\d+")


def _ident(v) -> dict:
    """Classify a lookup_value / subject_reference style string into a norm_keys raw dict."""
    s = str(v).strip() if v is not None else ""
    if "@" in s:
        return {"email": s}
    if USER.fullmatch(s):
        return {"user_id": s}
    return {"email_hash": s} if HEX64.fullmatch(s) else {}


def _flow(enabled) -> str:
    return "FLOW_ACTIVE" if enabled else "FLOW_DISABLED"


def _restore(allowed) -> str:
    return "RESTORE_OPEN" if allowed else "RESTORE_BLOCKED"


def _ledger(r):
    cat, res = r["record_type"], r["result"]
    if res == "ACTIVE":
        obs = "RESTORE_OPEN" if cat == "BACKUP_ARCHIVE" else "FLOW_ACTIVE"
    else:
        obs = LEDGER_STATE[res]
    field = "lookup_value" if "lookup_value" in r else "subject_reference"
    return cat, obs, _ident(r.get(field)), ({field} if res == "IDENTIFIABLE" else set())


def _exposure(cat, clean_obs, raw, own_ids=()):
    """REDACT/ANONYMIZE-category record: populated direct identifiers (minus stable refs) are exposed PII."""
    from .evidence import norm_keys
    pii = {k for k, _ in norm_keys(raw)} - set(own_ids)
    return cat, ("PRESENT" if pii else clean_obs), raw, pii


def _analytics(r):
    raw = {"user_id": r.get("user_id") or r.get("customer_reference"), "email": r.get("email"),
           "phone": r.get("phone"), "email_hash": r.get("email_hash")}
    return _exposure("ANALYTICS_PROFILE", "ANONYMIZED", raw)


def _support(r, raw):
    return _exposure("SUPPORT_MESSAGE", "REDACTED", raw, own_ids=("user_id",))


def _conversation(r):
    m = EMAIL_RE.search(str(r.get("message_text") or ""))
    return _support(r, {"user_id": r.get("subject_reference"), "email": m.group(0) if m else None})


def _ticket(r):
    return _support(r, {"user_id": r.get("customer_reference"), "email": r.get("requester_email"),
                        "name": r.get("requester_name"), "phone": r.get("requester_phone")})


def _tombstone(r):
    raw = {k: r.get(k) for k in ("name", "email", "phone", "email_hash")}
    cat, obs, _, pii = _exposure("ACCOUNT_TOMBSTONE", "REDACTED", raw)
    return cat, obs, dict(raw, user_id=r.get("subject_reference")), pii


def _profile(r):
    p = r.get("profile")
    if r.get("status_code") == 200 and p:
        return "USER_PROFILE", "PRESENT", {"email": p.get("email"), "name": p.get("full_name"), "phone": p.get("phone"),
                                           "email_hash": p.get("email_hash"), "user_id": p.get("customer_reference")}, set()
    return "USER_PROFILE", "ABSENT", {}, set()


def _query(r):
    hits = r["hits"]
    docs = hits.get("documents") or []
    raw = {"email": r.get("query")}
    if docs:
        raw = {"email": docs[0].get("email") or r.get("query"), "name": docs[0].get("display_name"),
               "user_id": docs[0].get("customer_reference")}
    return "SEARCH_INDEX_ENTRY", ("PRESENT" if hits.get("total", 0) >= 1 else "ABSENT"), raw, set()


def _simple(cat, obs_fn, **keymap):
    """keymap: norm_keys name -> record field."""
    return lambda r: (cat, obs_fn(r), {k: r.get(f) for k, f in keymap.items()}, set())


def _sel(r):
    return _ident(r.get("subject_selector"))


# collection (snapshot) or list (service export) name -> record handler
# -> (category, observation, raw identifier dict, pii field names)
HANDLERS = {
    "customer_profiles": _simple("USER_PROFILE", lambda r: "PRESENT", email="email", name="full_name", phone="phone",
                                 user_id="customer_reference"),
    "customer_search_documents": lambda r: ("SEARCH_INDEX_ENTRY", "PRESENT", {
        "email": r["document"].get("email"), "name": r["document"].get("display_name"),
        "user_id": r["document"].get("customer_reference")}, set()),
    "customer_analytics_reports": _analytics, "profiles": _analytics,
    "support_conversations": _conversation, "tickets": _ticket,
    "ticket_attachments": _simple("SUPPORT_ATTACHMENT", lambda r: "PRESENT", email="uploaded_by"),
    "customer_export_jobs": _simple("USER_EXPORT", lambda r: "PRESENT" if r.get("download_available") else "ABSENT",
                                    email="owner_email"),
    "exports": _simple("USER_EXPORT", lambda r: "PRESENT", email="owner_email", phone="owner_phone",
                       user_id="customer_reference"),
    "connector_configurations": lambda r: ("DATA_FLOW", _flow(r.get("enabled")), _sel(r), set()),
    "connectors": _simple("DATA_FLOW", lambda r: _flow(r.get("enabled")), email="customer_email",
                          user_id="customer_reference"),
    "backup_catalog": lambda r: ("BACKUP_ARCHIVE", _restore(r.get("restore_allowed")),
                                 _ident(r.get("subject_reference")), set()),
    "restore_entries": _simple("BACKUP_ARCHIVE", lambda r: _restore(r.get("restore_allowed")), email="customer_email",
                               user_id="customer_reference"),
    "deleted_customer_references": _tombstone,
    "security_audit_events": _simple("SECURITY_AUDIT_LOG", lambda r: "PRESENT", user_id="subject_reference"),
    "audit_records": _simple("SECURITY_AUDIT_LOG", lambda r: "PRESENT", user_id="subject_reference"),
    "retained_order_records": _simple("LEGAL_HOLD_RECORD", lambda r: "PRESENT", user_id="subject_reference"),
    "profile_lookups": _profile, "index_queries": _query,
    LEDGER: _ledger,
}


def parse(path: Path, meta: dict) -> tuple[list, list]:
    """-> (facts: list[evidence.Fact], coverage: list[evidence.Coverage]). Raise on malformed input."""
    from .evidence import Coverage, Fact, norm_keys, system_for
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    fid, cap = meta["file_id"], meta["captured_at"]
    # groups: (collection, default system or None, snapshot time, records, covers?)
    if "snapshots" in doc:
        groups = [(s["collection"], s["data_store"], s["captured_at"], s["records"], True) for s in doc["snapshots"]]
    elif "service_exports" in doc:
        groups = [(lst, sysid, cap, recs, False) for sysid, lists in doc["service_exports"].items()
                  for lst, recs in lists.items()]
    elif "records" in doc:
        groups = [(doc.get("collection", LEDGER), None, doc.get("captured_at", cap), doc["records"], False)]
    else:
        raise ValueError("unrecognised JSON evidence shape")
    facts, covered = [], {}
    for coll, default_sys, snap_at, recs, covers in groups:
        handler = HANDLERS.get(coll)
        if handler is None:
            raise ValueError(f"unknown collection {coll!r}")
        if covers and coll != LEDGER and any(g[3] for g in groups):
            covered[default_sys] = max(covered.get(default_sys, ""), snap_at)
        for r in recs:
            cat, obs, raw, pii = handler(r)
            rid = r["resource_id"]
            sysid = system_for(rid, r.get("system") or (None if coll == LEDGER else default_sys))
            if sysid is None:
                raise ValueError(f"no system for {rid}")
            facts.append(Fact(fid, "FILE", cap, r.get("observed_at") or r.get("recorded_at") or snap_at, sysid, rid, cat,
                              obs, norm_keys(raw), frozenset(pii)))
    facts.sort(key=lambda f: (f.evidence_id, f.system_id, f.resource_id, f.observation))
    return facts, [Coverage(fid, s, cap, t) for s, t in sorted(covered.items())]
