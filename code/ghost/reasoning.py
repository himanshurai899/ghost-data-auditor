"""S4-S6: temporal linking (G5), state reconstruction, policy evaluation (architecture.md §4.4)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceVerdict:
    system_id: str
    resource_id: str
    category: str
    rule_id: str
    required_state: str     # ABSENT | REDACTED | ANONYMIZED | PRESENT | DISABLED | BLOCKED
    current_state: str
    compliant: bool
    evidence_id: str        # fact proving current_state (<= audit_at)
    kind: str = "RECORD"    # RECORD | FLOW | RESTORE


def link(subject, facts, audit_at: str) -> list:
    """TODO(P1-09): facts matching any subject identifier with observed_at <= audit_at (hard filter)."""
    return []


def evaluate(facts, rules, audit_at: str) -> list[ResourceVerdict]:
    """TODO(P1-10, P1-11): latest observation per resource -> required state per deletion_rules.csv."""
    return []
