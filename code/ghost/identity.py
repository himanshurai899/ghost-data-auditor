"""S3 Identity: request email + audit_at -> Subject with current and historical identifiers (G4)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Subject:
    user_id: str
    emails: frozenset
    phones: frozenset
    email_hashes: frozenset    # sha256(email), dataset_facts F-003
    names: frozenset


def build_index():
    """TODO(P1-07): load user_identities.csv + user_audit_log.csv."""
    return None


def resolve(email: str, audit_at: str, index) -> Subject | None:
    """TODO(P1-07): replay audit log up to audit_at; None when unresolved (G4 WARN)."""
    return None
