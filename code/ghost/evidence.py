"""S1 Ingest: evidence files + activity + audit log -> normalized Fact rows (architecture.md §4.3)."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fact:
    evidence_id: str           # file_id | activity_id | audit_id (what gets cited)
    evidence_kind: str         # FILE | ACTIVITY | AUDIT
    observed_at: str           # ISO-8601 UTC
    system_id: str
    resource_id: str
    category: str              # deletion_rules.data_category
    observation: str           # PRESENT | ABSENT | REDACTED | ANONYMIZED | FLOW_ACTIVE | FLOW_DISABLED | RESTORE_OPEN | RESTORE_BLOCKED
    subject_keys: tuple = ()   # ((key, value), ...) e.g. (("email", "..."), ("user_id", "user_05"))
    pii_fields: frozenset = field(default_factory=frozenset)
    is_claim: bool = False     # activity reported_result / workflow status: never sufficient alone


def ingest(trail) -> tuple[list[Fact], list[str]]:
    """Return (facts, quarantined_file_ids). Every manifest file must be parsed or quarantined (G2).

    TODO(P1-05): SQL/JSON/log/TXT parsers via safety.safe_evidence_path + safety.open_sandboxed_sqlite.
    TODO(P1-06): activity + audit-log facts.  TODO(P2-02): PNG/PDF via llm vision.
    """
    return [], []
