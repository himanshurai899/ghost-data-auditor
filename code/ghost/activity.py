"""system_activity.csv -> Facts, all CLAIMS (F-018, field map §3). user_audit_log.csv is not turned into facts.

A claim never sets PRESENT/ABSENT/REDACTED/ANONYMIZED: DELETE/ANONYMIZE/REDACT/SYNC/RESTORE_BACKUP rows
carry `CLAIM_<EVENT>_<RESULT>` so `reported_result` is preserved without implying state. Flow/restore
checks map to the §1.4 vocabulary (FLOW_ACTIVE, ...) and still have is_claim=True.
"""
import re

from .contract import DATASET, read_csv

# event_type -> observation (None: build CLAIM_<EVENT>_<RESULT>)
HANDLED_OBS = {
    "CHECK_DATA_FLOW": "FLOW_ACTIVE", "DISABLE_DATA_FLOW": "FLOW_DISABLED",
    "CHECK_RESTORE_ACCESS": "RESTORE_OPEN", "BLOCK_RESTORE": "RESTORE_BLOCKED",
    "DELETE_RECORD": None, "ANONYMIZE_RECORD": None, "REDACT_RECORD": None,
    "SYNC_RECORD": None, "RESTORE_BACKUP": None, "LINK_RESOURCE_IDENTITY": None,
}
HANDLED = frozenset(HANDLED_OBS)
# Ignored with reason: background noise touching no case resource (§3), and CLASSIFY_REQUEST, whose
# non-deletion verdict comes from request_text (intent.py); it names an account, not a subject.
IGNORED = frozenset({"INDEX_RECORD", "UPDATE_RECORD", "REFRESH_CACHE", "SEND_EMAIL", "CREATE_EXPORT",
                     "RETAIN_RECORD", "CLASSIFY_REQUEST"})

PREFIX_CATEGORY = {
    "account_": "USER_PROFILE", "search_": "SEARCH_INDEX_ENTRY", "support_": "SUPPORT_MESSAGE",
    "analytics_": "ANALYTICS_PROFILE", "export_": "USER_EXPORT", "audit_record_": "SECURITY_AUDIT_LOG",
    "legal_hold_": "LEGAL_HOLD_RECORD", "backup_": "BACKUP_ARCHIVE", "tombstone_": "ACCOUNT_TOMBSTONE",
    "data_flow_": "DATA_FLOW", "marketing_": "MARKETING_PROFILE", "cache_": "CACHE_ENTRY",
    "email_delivery_": "EMAIL_DELIVERY_LOG",
}
LINK_RE = re.compile(r"(\S+@\S+?) and (user_\d+)[.;]")  # also "belongs only to <email> and user_07;"
DOWNSTREAM_RE = re.compile(r"downstream resource (\S+?)\.?$")


def _category(resource_id):
    return next((c for p, c in PREFIX_CATEGORY.items() if resource_id.startswith(p)), "")


def load(activity_rows=None, audit_rows=None) -> list:
    """Activity Facts sorted by (evidence_id, resource_id). `audit_rows` is accepted for the pipeline
    signature but unused: identity.py already consumes the audit log, and audit rows name no resource."""
    from .evidence import Fact, norm_keys, system_for  # lazy: evidence imports this module

    rows = read_csv(DATASET / "system_activity.csv") if activity_rows is None else activity_rows
    out = []
    for r in rows:
        et = r["event_type"]
        if et in IGNORED:
            continue
        if et not in HANDLED:
            raise ValueError(f"unhandled activity event_type {et!r} ({r['activity_id']})")
        keys = ()
        if et == "LINK_RESOURCE_IDENTITY":
            m = LINK_RE.search(r["details"])
            if m:
                keys = norm_keys({"email": m.group(1), "user_id": m.group(2)})
        obs = HANDLED_OBS[et] or f"CLAIM_{et}_{r['reported_result']}"
        targets = [r["resource_id"]]
        m = DOWNSTREAM_RE.search(r["details"]) if et in ("SYNC_RECORD", "RESTORE_BACKUP") else None
        if m:
            targets.append(m.group(1))
        for res in targets:
            out.append(Fact(r["activity_id"], "ACTIVITY", r["event_time"], r["event_time"],
                            system_for(res) or r["target_system"], res, _category(res), obs, keys,
                            is_claim=True))
    return sorted(out, key=lambda f: (f.evidence_id, f.resource_id))
