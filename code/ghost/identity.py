"""S3 Identity: request email + audit_at -> Subject with current and historical identifiers (G4)."""
import hashlib
from collections import defaultdict
from dataclasses import dataclass

from .contract import DATASET, read_csv, ts

IDENTITY_HEADER = ["user_id", "name", "email", "phone", "email_hash", "updated_at"]
AUDIT_HEADER = ["audit_id", "user_id", "event_time", "field_name", "old_value", "new_value"]
FIELDS = ("email", "phone", "email_hash", "name")


@dataclass(frozen=True)
class Subject:
    user_id: str
    emails: frozenset
    phones: frozenset
    email_hashes: frozenset    # sha256(email), dataset_facts F-003
    names: frozenset


def norm_email(email: str) -> str:
    # Stored emails are all lower-case with no whitespace; 20 requests differ only by case (F-004).
    return email.strip().lower()


def build_index(identities=None, audit_log=None) -> dict:
    """Current identity rows + time-ordered audit changes per user, and every email ever held -> user_ids."""
    if identities is None:
        identities = read_csv(DATASET / "user_identities.csv", IDENTITY_HEADER)
    if audit_log is None:
        audit_log = read_csv(DATASET / "user_audit_log.csv", AUDIT_HEADER)
    changes = defaultdict(list)
    for ch in audit_log:
        changes[ch["user_id"]].append(ch)
    users, by_email = {}, defaultdict(set)
    for row in identities:
        uid = row["user_id"]
        log = sorted(changes[uid], key=lambda ch: (ts(ch["event_time"]), ch["audit_id"]))
        users[uid] = (row, log)
        ever = [row["email"]] + [v for ch in log if ch["field_name"] == "email" for v in (ch["old_value"], ch["new_value"])]
        for e in ever:
            if e:
                by_email[norm_email(e)].add(uid)
    return {"users": users, "by_email": dict(by_email)}


def _as_of(row: dict, log: list, audit_at) -> tuple[dict, dict]:
    """(value held at audit_at, that value plus every value it replaced at or before audit_at) per field."""
    state = {f: row.get(f, "") for f in FIELDS}
    held = {f: set() for f in FIELDS}
    for ch in reversed(log):            # roll back changes that had not happened yet
        if ch["field_name"] in state and ts(ch["event_time"]) > audit_at:
            state[ch["field_name"]] = ch["old_value"]
    for ch in log:
        if ch["field_name"] in held and ts(ch["event_time"]) <= audit_at:
            held[ch["field_name"]].add(ch["old_value"])
    return state, {f: frozenset(v for v in held[f] | {state[f]} if v) for f in FIELDS}


def resolve(email: str, audit_at: str, index) -> Subject | None:
    """Subject for the request email as of audit_at; None when unknown or ambiguous (G4 WARN)."""
    key, at = norm_email(email), ts(audit_at)
    cands = sorted(index["by_email"].get(key, ())) if key else []
    asof = {uid: _as_of(*index["users"][uid], at) for uid in cands}
    if len(cands) > 1:   # prefer whoever held the email at audit_at
        cands = [uid for uid in cands if norm_email(asof[uid][0]["email"]) == key]
    if len(cands) != 1:
        return None
    v = asof[cands[0]][1]
    hashes = v["email_hash"] | {hashlib.sha256(e.encode("utf-8")).hexdigest() for e in v["email"]}
    return Subject(cands[0], v["email"], v["phone"], frozenset(hashes), v["name"])

