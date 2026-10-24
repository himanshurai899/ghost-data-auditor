import hashlib

from ghost import contract as c
from ghost import identity
from ghost.identity import Subject


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def ident(uid, name, email, phone):
    return {"user_id": uid, "name": name, "email": email, "phone": phone, "email_hash": h(email),
            "updated_at": "2026-01-01T00:00:00Z"}


def change(aid, uid, when, field, old, new):
    return {"audit_id": aid, "user_id": uid, "event_time": when, "field_name": field, "old_value": old,
            "new_value": new}


def email_change(n, uid, when, old, new):
    return [change(f"aud_{n}a", uid, when, "email", old, new),
            change(f"aud_{n}b", uid, when, "email_hash", h(old), h(new))]


# user_a: old.a -> mid.a (2025-03) -> new.a (2025-09); phone changed 2025-06.
IDENTS = [ident("user_a", "Ada Example", "new.a@example.com", "+1 555 0100"),
          ident("user_b", "Bo Example", "bo@example.org", "+1 555 0200")]
LOG = (email_change(1, "user_a", "2025-03-01T00:00:00Z", "old.a@example.com", "mid.a@example.com")
       + email_change(2, "user_a", "2025-09-01T00:00:00Z", "mid.a@example.com", "new.a@example.com")
       + [change("aud_3", "user_a", "2025-06-01T00:00:00Z", "phone", "+1 555 0199", "+1 555 0100")])
INDEX = identity.build_index(IDENTS, LOG)
LATE = "2026-01-01T00:00:00Z"   # after every change
MID = "2025-07-01T00:00:00Z"    # after the first email + phone change, before the second email change


def test_current_email_match():
    s = identity.resolve("bo@example.org", LATE, INDEX)
    assert s == Subject("user_b", frozenset({"bo@example.org"}), frozenset({"+1 555 0200"}),
                        frozenset({h("bo@example.org")}), frozenset({"Bo Example"}))


def test_historical_email_match_collects_all_past_values():
    s = identity.resolve("old.a@example.com", LATE, INDEX)
    assert s.user_id == "user_a"
    assert s.emails == {"old.a@example.com", "mid.a@example.com", "new.a@example.com"}
    assert all(isinstance(getattr(s, f), frozenset) for f in ("emails", "phones", "email_hashes", "names"))


def test_change_after_audit_at_is_excluded():
    s = identity.resolve("mid.a@example.com", MID, INDEX)
    assert s.user_id == "user_a"
    assert s.emails == {"old.a@example.com", "mid.a@example.com"}   # new.a did not exist yet
    assert h("new.a@example.com") not in s.email_hashes
    early = identity.resolve("old.a@example.com", "2025-01-01T00:00:00Z", INDEX)
    assert early.emails == {"old.a@example.com"} and early.phones == {"+1 555 0199"}


def test_change_exactly_at_audit_at_is_included():
    s = identity.resolve("new.a@example.com", "2025-09-01T00:00:00Z", INDEX)
    assert "new.a@example.com" in s.emails


def test_hash_derivation_covers_every_email():
    s = identity.resolve("new.a@example.com", LATE, INDEX)
    assert s.email_hashes == {h(e) for e in s.emails}
    # A recorded hash is kept even when no email in the set produces it.
    odd = identity.build_index([{**IDENTS[1], "email_hash": "f" * 64}], [])
    assert identity.resolve("bo@example.org", LATE, odd).email_hashes == {"f" * 64, h("bo@example.org")}


def test_phone_history():
    assert identity.resolve("new.a@example.com", LATE, INDEX).phones == {"+1 555 0199", "+1 555 0100"}
    assert identity.resolve("new.a@example.com", "2025-05-01T00:00:00Z", INDEX).phones == {"+1 555 0199"}


def test_email_match_ignores_case_and_surrounding_whitespace():
    assert identity.resolve("  BO@Example.ORG ", LATE, INDEX).user_id == "user_b"


def test_shared_email_prefers_holder_at_audit_at():
    # shared@ belonged to user_c until 2025-05, then user_d took it.
    idents = [ident("user_c", "Cy Example", "cy@example.com", ""),
              ident("user_d", "Di Example", "shared@example.com", "")]
    log = (email_change(1, "user_c", "2025-05-01T00:00:00Z", "shared@example.com", "cy@example.com")
           + email_change(2, "user_d", "2025-06-01T00:00:00Z", "di@example.com", "shared@example.com"))
    idx = identity.build_index(idents, log)
    assert identity.resolve("shared@example.com", "2025-04-01T00:00:00Z", idx).user_id == "user_c"
    assert identity.resolve("shared@example.com", LATE, idx).user_id == "user_d"
    # Between the two changes nobody holds it: ambiguous.
    assert identity.resolve("shared@example.com", "2025-05-15T00:00:00Z", idx) is None


def test_ambiguous_email_returns_none():
    idx = identity.build_index([ident("user_e", "E", "dup@example.com", ""),
                                ident("user_f", "F", "dup@example.com", "")], [])
    assert identity.resolve("dup@example.com", LATE, idx) is None


def test_unknown_email_returns_none():
    assert identity.resolve("nobody@example.net", LATE, INDEX) is None
    assert identity.resolve("", LATE, INDEX) is None


def test_real_requests_all_resolve():
    # All 518 resolve once matching is case-insensitive: the 20 unmatched in F-004 are upper-cased
    # variants of stored emails (every stored email is already lower-case with no whitespace).
    idx = identity.build_index()
    reqs = c.load_requests(c.DATASET / "deletion_requests.csv")
    resolved = [identity.resolve(r["email"], r["audit_at"], idx) for r in reqs]
    assert len(reqs) == 518 and sum(s is not None for s in resolved) == 518
    assert sum(r["email"] != r["email"].lower() for r in reqs) == 20


def test_sample_requests_all_resolve():
    idx = identity.build_index()
    reqs = c.load_requests(c.DATASET / "sample_deletion_requests.csv")
    assert len(reqs) == 32 and all(identity.resolve(r["email"], r["audit_at"], idx) for r in reqs)
