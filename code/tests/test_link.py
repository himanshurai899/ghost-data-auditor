import pytest

from ghost import evidence as ev
from ghost.identity import Subject
from ghost.reasoning import Linked, link

REQ, AUD = "2026-03-10T00:00:00Z", "2026-04-01T00:00:00Z"
EARLY, MID, LATE = "2026-02-01T00:00:00Z", "2026-03-20T00:00:00Z", "2026-05-01T00:00:00Z"
SUBJ = Subject("user_9", frozenset({"a@example.com", "old@example.com"}), frozenset({"15550100"}),
               frozenset({"abc123"}), frozenset({"Alex Test"}))


def fact(rid, keys, cap=MID, obs=MID, eid=None, claim=False, system="account_service"):
    return ev.Fact(eid or f"f_{rid}_{cap[:7]}", "FILE", cap, obs, system, rid, "ACCOUNT", "PRESENT",
                   ev.norm_keys(keys), is_claim=claim)


@pytest.mark.parametrize("keys", [{"user_id": "user_9"}, {"email": "A@Example.com"}, {"email": "old@example.com"},
                                  {"phone": "+1 555-0100"}, {"email_hash": "ABC123"}])
def test_links_by_each_identifier(keys):
    assert link(SUBJ, [fact("r1", keys)], REQ, AUD).resources == {("account_service", "r1")}


def test_name_and_other_ids_never_link():
    out = link(SUBJ, [fact("r1", {"name": "Alex Test"}), fact("r2", {"user_id": "user_10"})], REQ, AUD)
    assert out.resources == frozenset() and out.facts == ()


def test_pre_request_link_is_decoy():
    assert link(SUBJ, [fact("r1", {"user_id": "user_9"}, obs=EARLY, cap=EARLY)], REQ, AUD).resources == frozenset()


def test_claim_without_keys_does_not_discover_but_keyed_claim_does():
    assert link(SUBJ, [fact("r1", {}, claim=True)], REQ, AUD).resources == frozenset()
    assert ("account_service", "r1") in link(SUBJ, [fact("r1", {"user_id": "user_9"}, claim=True)], REQ, AUD).resources


def test_unlinked_fact_of_discovered_resource_is_cited_if_citable():
    out = link(SUBJ, [fact("r1", {"user_id": "user_9"}, eid="a"), fact("r1", {}, eid="b")], REQ, AUD)
    assert [f.evidence_id for f in out.facts] == ["a", "b"]


def test_late_only_discovery_default_vs_strict_and_state_ignores_late():
    late = fact("r1", {"user_id": "user_9"}, cap=LATE, obs=LATE)  # case_09-type: resource known only from a late file
    d = link(SUBJ, [late], REQ, AUD)
    assert d.resources == {("account_service", "r1")} and d.late_only == d.resources and d.facts == ()
    s = link(SUBJ, [late], REQ, AUD, strict_temporal=True)
    assert s == Linked(frozenset(), (), frozenset())


def test_late_file_not_late_only_when_citable_link_exists():
    ok, late = fact("r1", {"user_id": "user_9"}, eid="ok"), fact("r1", {"user_id": "user_9"}, cap=LATE, eid="late")
    out = link(SUBJ, [late, ok], REQ, AUD)
    assert out.late_only == frozenset() and [f.evidence_id for f in out.facts] == ["ok"]


def test_never_cites_after_audit_and_boundary_inclusive():
    on = fact("r1", {"user_id": "user_9"}, cap=AUD, obs=MID, eid="on")
    late = fact("r1", {"user_id": "user_9"}, cap=LATE, eid="late")
    for strict in (False, True):
        assert [f.evidence_id for f in link(SUBJ, [late, on], REQ, AUD, strict).facts] == ["on"]


def test_deterministic_order():
    fs = [fact(f"r{i}", {"user_id": "user_9"}, eid=f"e{i}") for i in range(5)]
    assert link(SUBJ, fs, REQ, AUD) == link(SUBJ, fs[::-1], REQ, AUD)
