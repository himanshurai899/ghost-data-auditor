import pytest

from ghost import activity, evidence as ev
from ghost.contract import DATASET, read_csv

T = "2026-05-01T10:00:00Z"


def row(i, event, res, result="SUCCESS", src="deletion_worker", tgt="account_service", details="x"):
    return {"activity_id": i, "event_time": T, "event_type": event, "source_system": src,
            "target_system": tgt, "resource_id": res, "reported_result": result, "details": details}


def one(r):
    (f,) = activity.load([r], [])
    return f


def test_flow_and_restore_claims():
    f = one(row("a1", "CHECK_DATA_FLOW", "data_flow_1", tgt="integration_service"))
    assert (f.observation, f.system_id, f.category) == ("FLOW_ACTIVE", "integration_service", "DATA_FLOW")
    assert one(row("a2", "DISABLE_DATA_FLOW", "data_flow_1")).observation == "FLOW_DISABLED"
    assert one(row("a3", "CHECK_RESTORE_ACCESS", "backup_1")).observation == "RESTORE_OPEN"
    assert one(row("a4", "BLOCK_RESTORE", "backup_1")).observation == "RESTORE_BLOCKED"
    assert one(row("a4", "BLOCK_RESTORE", "backup_1")).category == "BACKUP_ARCHIVE"


def test_every_fact_is_a_claim_and_never_state_from_result():
    for ev_type in ("DELETE_RECORD", "ANONYMIZE_RECORD", "REDACT_RECORD", "SYNC_RECORD"):
        for res in ("SUCCESS", "FAILED", "PARTIAL"):
            f = one(row("a1", ev_type, "account_9", res))
            assert f.is_claim and f.evidence_kind == "ACTIVITY" and f.evidence_id == "a1"
            assert f.observation not in {"PRESENT", "ABSENT", "REDACTED", "ANONYMIZED"}
            assert res in f.observation and ev_type in f.observation
            assert f.captured_at == f.observed_at == T


def test_replica_sync_system_is_account_service():
    f = one(row("a1", "SYNC_RECORD", "account_9", src="account_service", tgt="account_replication_cluster"))
    assert f.system_id == "account_service"


def test_link_row_gives_subject_keys():
    d = "Data catalog linked search_7 (search_7) to Jane.Doe@Example.com and user_42."
    f = one(row("a1", "LINK_RESOURCE_IDENTITY", "search_7", src="data_catalog", tgt="search_service", details=d))
    assert f.subject_keys == (("email", "jane.doe@example.com"), ("user_id", "user_42"))
    assert f.is_claim


def test_downstream_repopulation_fact():
    d = "Active connector repopulated downstream resource search_2."
    fs = activity.load([row("a1", "SYNC_RECORD", "data_flow_1", src="integration_service", tgt="search_service", details=d)], [])
    assert {f.resource_id for f in fs} == {"data_flow_1", "search_2"}


def test_noise_ignored_and_deterministic_order():
    rows = [row("a2", "DELETE_RECORD", "account_1"), row("a1", "DELETE_RECORD", "account_2"),
            row("a3", "INDEX_RECORD", "search_1"), row("a4", "CLASSIFY_REQUEST", "account_1")]
    assert [f.evidence_id for f in activity.load(rows, [])] == ["a1", "a2"]


def test_unknown_event_type_raises():
    with pytest.raises(ValueError):
        activity.load([row("a1", "NEW_EVENT", "account_1")], [])


def test_ingest_appends_activity_facts():
    class Trail:
        def event(self, *a, **k):
            pass
    facts, cov, quar = ev.ingest(Trail(), manifest=[], parsers={})
    assert any(f.evidence_kind == "ACTIVITY" for f in facts) and not cov and not quar


def test_real_dataset_all_event_types_handled():
    rows = read_csv(DATASET / "system_activity.csv")
    assert len(rows) == 4011
    assert {r["event_type"] for r in rows} == activity.HANDLED | activity.IGNORED
    facts = activity.load()
    assert all(f.is_claim for f in facts)
    links = [f for f in facts if f.subject_keys]
    assert len(links) == 12 and all(dict(f.subject_keys).get("user_id") for f in links)
