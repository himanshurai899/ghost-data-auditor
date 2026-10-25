"""S1 Ingest: evidence files -> normalized Fact rows + table-level Coverage (architecture.md §4.3).

Shared contract for the per-family parsers (ev_sql, ev_json, ev_text), as specified in
docs/evidence_field_map.md §1. A parser is `parse(path, meta) -> (facts, coverage)` where `meta` is the
evidence_files.csv row; it raises on malformed input and the file is quarantined (G2).
"""
import re
from dataclasses import dataclass, field

from . import ev_json, ev_page, ev_sql, ev_text
from .contract import DATASET, read_csv
from .safety import UnsafeInput, safe_evidence_path

PREFIX_SYSTEM = {
    "account_": "account_service", "search_": "search_service", "support_": "support_platform",
    "analytics_": "analytics_platform", "export_": "export_service", "marketing_": "marketing_platform",
    "backup_": "backup_service", "data_flow_": "integration_service", "audit_record_": "security_service",
    "tombstone_": "identity_service", "legal_hold_": "legal_service", "object_": "object_storage",
}
NULL_TOKENS = {"", "null", "none", "[redacted]"}
KEY_FIELDS = ("email", "email_hash", "name", "phone", "user_id")


@dataclass(frozen=True)
class Fact:
    evidence_id: str           # file_id | activity_id | audit_id (what gets cited)
    evidence_kind: str         # FILE | ACTIVITY | AUDIT
    captured_at: str           # manifest capture time: decides citability (F-013)
    observed_at: str           # row time > snapshot time > captured_at (field map §1.3)
    system_id: str
    resource_id: str
    category: str              # deletion_rules.data_category, or DATA_FLOW for connectors
    observation: str           # PRESENT | ABSENT | REDACTED | ANONYMIZED | FLOW_ACTIVE | FLOW_DISABLED | RESTORE_OPEN | RESTORE_BLOCKED
    subject_keys: tuple = ()   # norm_keys(...) output: sorted ((key, value), ...)
    pii_fields: frozenset = field(default_factory=frozenset)  # direct identifiers still populated
    is_claim: bool = False     # activity reported_result / workflow status: never sufficient alone


@dataclass(frozen=True)
class Coverage:
    """A full table-level snapshot of a system: omission of a resource here proves ABSENT (F-012)."""
    evidence_id: str
    system_id: str
    captured_at: str
    observed_at: str


def system_for(resource_id: str, explicit: str | None = None) -> str | None:
    if explicit and not is_null(explicit):
        return explicit
    return next((s for p, s in PREFIX_SYSTEM.items() if resource_id.startswith(p)), None)


def is_null(value) -> bool:
    return value is None or str(value).strip().lower() in NULL_TOKENS


def norm_keys(raw: dict) -> tuple:
    """Subject keys from a raw record: email/email_hash lower-cased, phone digits only, nulls dropped."""
    out = {}
    for k in KEY_FIELDS:
        v = raw.get(k)
        if is_null(v):
            continue
        v = str(v).strip()
        out[k] = v.lower() if k in ("email", "email_hash") else re.sub(r"\D", "", v) if k == "phone" else v
    return tuple(sorted(out.items()))


def ingest(trail, manifest=None, parsers=None) -> tuple[list[Fact], list[Coverage], list[tuple[str, str]]]:
    """Parse every manifest file. Returns (facts, coverage, quarantined[(file_id, reason)])."""
    manifest = read_csv(DATASET / "evidence_files.csv") if manifest is None else manifest
    parsers = parsers or {".sql": ev_sql.parse, ".json": ev_json.parse, ".log": ev_text.parse, ".txt": ev_text.parse,
                         ".png": ev_page.parse, ".pdf": ev_page.parse}
    facts, coverage, quarantined = [], [], []
    for meta in manifest:
        fid = meta["file_id"]
        try:
            path = safe_evidence_path(meta["file_path"])
        except UnsafeInput as e:
            quarantined.append((fid, str(e)))
            continue
        suffix = path.suffix.lower()
        if suffix not in parsers:
            quarantined.append((fid, f"no parser for {suffix}"))
            continue
        try:
            f, c = parsers[suffix](path, meta)
        except Exception as e:  # any parser failure quarantines that file only; G2 decides if the run survives
            quarantined.append((fid, f"{type(e).__name__}: {e}"))
            continue
        facts += f
        coverage += c
    from . import activity  # lazy: activity imports Fact from this module
    facts += activity.load()
    for fid, reason in quarantined:
        trail.event("ingest", f"Quarantined {fid}: {reason}", verdict="WARN")
    return facts, coverage, quarantined
