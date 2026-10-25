"""S4-S6: temporal linking (G5), state reconstruction, policy evaluation (architecture.md §4.4)."""
import re
from dataclasses import dataclass, field

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
    pii_fields: frozenset = field(default_factory=frozenset)  # direct identifiers still populated in the cited row
    claim_only: bool = False  # state rests on an activity claim (evidence_id is "": claims are never cited)


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


_OBS_STATE = {"PRESENT": "PRESENT", "ABSENT": "ABSENT", "REDACTED": "REDACTED", "ANONYMIZED": "ANONYMIZED",
              "FLOW_ACTIVE": "ACTIVE", "FLOW_DISABLED": "DISABLED", "RESTORE_OPEN": "ACTIVE", "RESTORE_BLOCKED": "BLOCKED"}
_ACTION_STATE = {"DELETE": "ABSENT", "REDACT": "REDACTED", "ANONYMIZE": "ANONYMIZED", "RETAIN": "PRESENT"}
_RANK = {"PRESENT": 3, "ACTIVE": 3, "REDACTED": 2, "ANONYMIZED": 2, "BLOCKED": 1, "DISABLED": 1, "ABSENT": 0}
# Policy beyond deletion_rules.csv: category -> (rule_id, required_state, kind). Connectors have no rule row; the
# backup rule's action is RETAIN but its condition ("restore access can be blocked") means restore must be BLOCKED.
_SPECIAL = {"DATA_FLOW": ("", "DISABLED", "FLOW"), "BACKUP_ARCHIVE": (None, "BLOCKED", "RESTORE")}
_STABLE_REF_OK = {"SUPPORT_MESSAGE", "ACCOUNT_TOMBSTONE", "EMAIL_DELIVERY_LOG"}  # user_id / customer_reference allowed


def _policy(category: str, rules) -> tuple[str, str, str]:
    """(rule_id, required_state, kind). Unknown categories (open item: analytics_9914, support_002) -> DELETE."""
    rule = next((r for r in rules if r["data_category"] == category), None)
    if category in _SPECIAL:
        rid, state, kind = _SPECIAL[category]
        return (rule["rule_id"] if rule and rid is None else rid or ""), state, kind
    if rule:
        return rule["rule_id"], _ACTION_STATE[rule["required_action"].strip().upper()], "RECORD"
    return "", "ABSENT", "RECORD"


def _compliant(required: str, current: str, pii: frozenset) -> bool:
    if current == "UNKNOWN":
        return True  # nothing proves a violation (claims never set record state)
    if required in ("REDACTED", "ANONYMIZED"):
        # ponytail: a deleted record counts as compliant here (no PII left); revisit if samples disagree
        return current in (required, "ABSENT") and not pii
    return current == required


def evaluate(facts, rules, audit_at: str, coverage=(), all_facts=None) -> list[ResourceVerdict]:
    """S5+S6. Per (system, resource): latest citable file observation wins (ties: PRESENT beats ABSENT, then later
    evidence_id); activity claims only raise FLOW/RESTORE risks no file contradicts; omission from a later citable
    table-level snapshot proves ABSENT (F-012). Sorted by (system_id, resource_id)."""
    aud = ts(audit_at)
    cites = [f for f in facts if ts(f.captured_at) <= aud]
    cov = [c for c in coverage if ts(c.captured_at) <= aud]
    in_file = {}  # evidence_id -> resources it holds a row for
    for f in cites:
        in_file.setdefault(f.evidence_id, set()).add((f.system_id, f.resource_id))
    in_all = {}  # same, over every case's facts: lets a resource with no file row of its own use a snapshot (orphans)
    for f in (cites if all_facts is None else (g for g in all_facts if ts(g.captured_at) <= aud)):
        in_all.setdefault(f.evidence_id, set()).add((f.system_id, f.resource_id))
    groups = {}
    for f in cites:
        groups.setdefault((f.system_id, f.resource_id), []).append(f)

    out = []
    for (sys_id, res_id), fs in sorted(groups.items()):
        # Record kind comes from the evidence file that observed the record; the id-prefix guess carried by activity
        # claims (support_* -> SUPPORT_MESSAGE, analytics_* -> ANALYTICS_PROFILE) is only a fallback: an attachment,
        # contact index or marketing-style row shares its system's prefix but has a different (DELETE) rule.
        category = next((f.category for f in sorted(fs, key=lambda f: f.is_claim) if f.category), "")
        rule_id, required, kind = _policy(category, rules)
        obs = sorted((f for f in fs if not f.is_claim and f.observation in _OBS_STATE),
                     key=lambda f: (ts(f.observed_at), _RANK[_OBS_STATE[f.observation]], f.evidence_id))
        cur, ev, pii, claim_only = "UNKNOWN", "", frozenset(), False
        latest = ts(obs[-1].observed_at) if obs else None
        omit = []
        if kind == "RECORD":  # omission from a later, non-empty snapshot of the same system
            pool = in_file if (obs or required == "PRESENT") else in_all
            omit = sorted((c for c in cov if c.system_id == sys_id and pool.get(c.evidence_id)
                           and (sys_id, res_id) not in pool[c.evidence_id]
                           and (latest is None or ts(c.observed_at) > latest)),
                          key=lambda c: (ts(c.captured_at), c.evidence_id))
        if omit:
            cur, ev = "ABSENT", omit[-1].evidence_id
        elif obs:
            cur = _OBS_STATE[obs[-1].observation]
            proof = sorted((f for f in obs if _OBS_STATE[f.observation] == cur),
                           key=lambda f: (ts(f.captured_at), ts(f.observed_at), f.evidence_id))[-1]
            ev, pii = proof.evidence_id, proof.pii_fields
        elif kind != "RECORD":  # risk claims only, and no citable file observation contradicts them
            risk = "FLOW_ACTIVE" if kind == "FLOW" else "RESTORE_OPEN"
            if any(f.is_claim and f.observation == risk for f in fs):
                cur, claim_only = "ACTIVE", True
        if category in _STABLE_REF_OK:
            pii = frozenset(pii) - {"user_id"}
        out.append(ResourceVerdict(sys_id, res_id, category, rule_id, required, cur,
                                   _compliant(required, cur, pii), ev, kind, frozenset(pii), claim_only))
    return out
