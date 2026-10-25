"""S4-S6: temporal linking (G5), state reconstruction, policy evaluation (architecture.md §4.4)."""
import re
from dataclasses import dataclass

from .contract import ts


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


@dataclass(frozen=True)
class Linked:
    resources: frozenset      # (system_id, resource_id) belonging to the case
    facts: tuple              # citable facts (captured_at <= audit_at) for those resources, sorted
    late_only: frozenset      # resources discovered only via files captured after audit_at (default mode)


def _subject_keys(subject) -> set:
    return ({("user_id", subject.user_id)} | {("email", e.lower()) for e in subject.emails}
            | {("phone", re.sub(r"\D", "", p)) for p in subject.phones}
            | {("email_hash", h.lower()) for h in subject.email_hashes})


def link(subject, facts, requested_at: str, audit_at: str, strict_temporal: bool = False) -> Linked:
    """G5. Discovery: a subject-linking fact observed at/after requested_at (F-014); late files count unless
    strict. State/citation: only facts captured at/before audit_at (F-013), inclusive, never relaxed."""
    keys, req, aud = _subject_keys(subject), ts(requested_at), ts(audit_at)
    found, found_citable = set(), set()
    for f in facts:
        if keys.isdisjoint(f.subject_keys) or ts(f.observed_at) < req:
            continue
        citable = ts(f.captured_at) <= aud
        if citable or not strict_temporal:
            found.add((f.system_id, f.resource_id))
        if citable:
            found_citable.add((f.system_id, f.resource_id))
    cited = sorted((f for f in facts if (f.system_id, f.resource_id) in found and ts(f.captured_at) <= aud),
                   key=lambda f: (f.system_id, f.resource_id, ts(f.observed_at), f.evidence_id))
    return Linked(frozenset(found), tuple(cited), frozenset(found - found_citable))


def evaluate(facts, rules, audit_at: str) -> list[ResourceVerdict]:
    """TODO(P1-10, P1-11): latest observation per resource -> required state per deletion_rules.csv."""
    return []
