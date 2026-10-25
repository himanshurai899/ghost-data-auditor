import csv
import json

import pytest

from ghost import ev_json
from ghost.contract import DATASET

META = {"file_id": "evidence_77", "file_path": "x.json", "origin": "t", "captured_at": "2026-09-10T00:00:00Z"}
SNAP_AT = "2026-09-09T12:00:00Z"


def run(tmp_path, doc, meta=META):
    p = tmp_path / "f.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return ev_json.parse(p, meta)


def bundle(*snaps):
    return {"exported_at": "2026-09-10T00:00:00Z", "source": "t",
            "snapshots": [{"captured_at": SNAP_AT, "data_store": ds, "collection": col, "records": recs}
                          for ds, col, recs in snaps]}


def svc(system, listname, recs):
    return {"exported_at": "x", "region": "r", "source": "t", "service_exports": {system: {listname: recs}}}


def one(facts, rid):
    got = [f for f in facts if f.resource_id == rid]
    assert len(got) == 1
    return got[0]


def test_bundle_profile_and_search_and_common_fields(tmp_path):
    doc = bundle(
        ("account_service", "customer_profiles", [{"resource_id": "account_1", "customer_reference": "user_1",
            "full_name": "Ann Test", "email": "ANN@Example.COM", "phone": "+1 555-0100", "account_status": "ACTIVE"}]),
        ("search_service", "customer_search_documents", [{"resource_id": "search_1", "index_name": "i",
            "document": {"display_name": None, "email": "ann@example.com", "customer_reference": "user_1"}}]))
    facts, cov = run(tmp_path, doc)
    a = one(facts, "account_1")
    assert (a.evidence_id, a.evidence_kind, a.captured_at, a.observed_at) == ("evidence_77", "FILE", META["captured_at"], SNAP_AT)
    assert (a.system_id, a.category, a.observation, a.is_claim) == ("account_service", "USER_PROFILE", "PRESENT", False)
    assert dict(a.subject_keys) == {"email": "ann@example.com", "name": "Ann Test", "phone": "15550100", "user_id": "user_1"}
    assert a.pii_fields == frozenset()  # DELETE-category record: pii_fields only for REDACT/ANONYMIZE categories
    s = one(facts, "search_1")
    assert (s.system_id, s.category, s.observation) == ("search_service", "SEARCH_INDEX_ENTRY", "PRESENT")
    assert dict(s.subject_keys) == {"email": "ann@example.com", "user_id": "user_1"}
    assert sorted(facts, key=lambda f: (f.evidence_id, f.system_id, f.resource_id, f.observation)) == facts


def test_coverage_for_snapshot_collections_even_empty_but_not_empty_file(tmp_path):
    doc = bundle(("account_service", "customer_profiles", []),
                 ("security_service", "security_audit_events", [{"resource_id": "audit_record_1",
                  "subject_reference": "user_1", "event_name": "e", "actor_type": "a", "integrity_seal": "s"}]))
    facts, cov = run(tmp_path, doc)
    assert {(c.system_id, c.evidence_id, c.captured_at, c.observed_at) for c in cov} == {
        ("account_service", "evidence_77", META["captured_at"], SNAP_AT),
        ("security_service", "evidence_77", META["captured_at"], SNAP_AT)}
    assert one(facts, "audit_record_1").category == "SECURITY_AUDIT_LOG"
    facts, cov = run(tmp_path, bundle(("account_service", "customer_profiles", [])))
    assert facts == [] and cov == []  # no data row anywhere: proves nothing


def test_ledger_collections_never_cover_and_use_record_system(tmp_path):
    rows = [
        {"recorded_at": "2026-09-01T00:00:00Z", "system": "account_service", "resource_id": "account_1",
         "record_type": "USER_PROFILE", "result": "NOT_FOUND", "lookup_value": "u@example.com"},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "search_service", "resource_id": "search_1",
         "record_type": "SEARCH_INDEX_ENTRY", "result": "FOUND", "lookup_value": "user_9"},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "support_platform", "resource_id": "support_1",
         "record_type": "SUPPORT_MESSAGE", "result": "IDENTIFIABLE", "lookup_value": "U2@EXAMPLE.COM"},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "support_platform", "resource_id": "support_2",
         "record_type": "SUPPORT_MESSAGE", "result": "REDACTED", "lookup_value": "user_9"},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "analytics_platform", "resource_id": "analytics_1",
         "record_type": "ANALYTICS_PROFILE", "result": "ANONYMIZED", "lookup_value": ""},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "integration_service", "resource_id": "data_flow_1",
         "record_type": "DATA_FLOW", "result": "ACTIVE", "lookup_value": "user_9"},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "integration_service", "resource_id": "data_flow_2",
         "record_type": "DATA_FLOW", "result": "DISABLED", "lookup_value": "user_9"},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "backup_service", "resource_id": "backup_1",
         "record_type": "BACKUP_ARCHIVE", "result": "ACTIVE", "lookup_value": "user_9"},
        {"recorded_at": "2026-09-02T00:00:00Z", "system": "backup_service", "resource_id": "backup_2",
         "record_type": "BACKUP_ARCHIVE", "result": "BLOCKED", "lookup_value": "user_9"}]
    # wrong data_store on purpose: the record's own system wins
    facts, cov = run(tmp_path, bundle(("backup_restore_service", "operational_record_history", rows)))
    assert cov == []
    a = one(facts, "account_1")
    assert (a.system_id, a.observation, a.observed_at, a.category) == ("account_service", "ABSENT", "2026-09-01T00:00:00Z", "USER_PROFILE")
    assert dict(a.subject_keys) == {"email": "u@example.com"}
    assert one(facts, "search_1").observation == "PRESENT"
    assert dict(one(facts, "search_1").subject_keys) == {"user_id": "user_9"}
    s1 = one(facts, "support_1")
    assert s1.observation == "PRESENT" and s1.pii_fields and dict(s1.subject_keys) == {"email": "u2@example.com"}
    assert one(facts, "support_2").observation == "REDACTED" and not one(facts, "support_2").pii_fields
    an = one(facts, "analytics_1")
    assert an.observation == "ANONYMIZED" and an.subject_keys == ()
    assert (one(facts, "data_flow_1").observation, one(facts, "data_flow_1").category) == ("FLOW_ACTIVE", "DATA_FLOW")
    assert one(facts, "data_flow_2").observation == "FLOW_DISABLED"
    assert one(facts, "backup_1").observation == "RESTORE_OPEN"
    assert one(facts, "backup_2").observation == "RESTORE_BLOCKED"
    assert one(facts, "backup_1").category == "BACKUP_ARCHIVE"


def test_flat_ledger_file(tmp_path):
    doc = {"exported_at": "x", "origin": "o", "record_count": 2, "records": [
        {"recorded_at": "2026-08-01T00:00:00Z", "system": "account_service", "resource_id": "account_2",
         "record_type": "USER_PROFILE", "result": "FOUND", "subject_reference": "user_2"},
        {"recorded_at": "2026-08-01T00:00:00Z", "system": "security_service", "resource_id": "audit_record_2",
         "record_type": "SECURITY_AUDIT_LOG", "result": "FOUND", "subject_reference": ""}]}
    facts, cov = run(tmp_path, doc)
    assert cov == [] and len(facts) == 2
    assert dict(one(facts, "account_2").subject_keys) == {"user_id": "user_2"}
    assert one(facts, "audit_record_2").subject_keys == ()


def test_analytics_anonymized_vs_exposed_and_null_tokens(tmp_path):
    base = {"reporting_window": "w", "metrics": {}, "recent_activity": []}
    doc = bundle(("analytics_platform", "customer_analytics_reports", [
        dict(base, resource_id="analytics_1", user_id=None, email=None, phone=None, email_hash=None),
        dict(base, resource_id="analytics_2", user_id="null", email="[REDACTED]", phone="", email_hash=None),
        dict(base, resource_id="analytics_3", user_id="user_3", email="A3@EXAMPLE.COM", phone="555 0103", email_hash="AB" * 32)]))
    facts, _ = run(tmp_path, doc)
    assert one(facts, "analytics_1").observation == "ANONYMIZED"
    assert one(facts, "analytics_2").observation == "ANONYMIZED"
    assert one(facts, "analytics_2").subject_keys == ()
    e = one(facts, "analytics_3")
    assert e.observation == "PRESENT" and e.category == "ANALYTICS_PROFILE"
    assert e.pii_fields == {"email", "phone", "email_hash", "user_id"}
    assert dict(e.subject_keys) == {"email": "a3@example.com", "email_hash": "ab" * 32, "phone": "5550103", "user_id": "user_3"}


def test_support_conversation_and_attachment_and_tombstone_and_legal(tmp_path):
    doc = bundle(
        ("support_platform", "support_conversations", [
            {"resource_id": "support_1", "ticket_id": "t", "subject_reference": "user_4", "channel": "c",
             "message_text": "Please call, my mail is Z@Example.com thanks"},
            {"resource_id": "support_2", "ticket_id": "t", "subject_reference": "user_4", "channel": "c",
             "message_text": "[REDACTED]"}]),
        ("support_platform", "ticket_attachments", [
            {"resource_id": "support_3", "ticket_id": "t", "file_name": "a.pdf", "storage_class": "s",
             "uploaded_by": "UP@example.com"}]),
        ("identity_service", "deleted_customer_references", [
            {"resource_id": "tombstone_1", "subject_reference": "user_5", "name": "N", "email": "t@example.com",
             "phone": "5550105", "email_hash": "cd" * 32, "account_status": "DELETED"},
            {"resource_id": "tombstone_2", "subject_reference": "user_6", "name": None, "email": None,
             "phone": None, "email_hash": None, "account_status": "DELETED"}]),
        ("legal_service", "retained_order_records", [
            {"resource_id": "legal_hold_1", "subject_reference": "user_7", "order_reference": "o",
             "retention_reason": "r", "retained_until": "2030-01-01T00:00:00Z"}]))
    facts, cov = run(tmp_path, doc)
    s1 = one(facts, "support_1")
    assert s1.observation == "PRESENT" and s1.pii_fields == {"email"} and s1.category == "SUPPORT_MESSAGE"
    assert dict(s1.subject_keys) == {"email": "z@example.com", "user_id": "user_4"}
    s2 = one(facts, "support_2")
    assert s2.observation == "REDACTED" and s2.pii_fields == frozenset() and dict(s2.subject_keys) == {"user_id": "user_4"}
    s3 = one(facts, "support_3")
    assert (s3.category, s3.observation) == ("SUPPORT_ATTACHMENT", "PRESENT")
    assert dict(s3.subject_keys) == {"email": "up@example.com"}
    t1, t2 = one(facts, "tombstone_1"), one(facts, "tombstone_2")
    assert (t1.system_id, t1.category, t1.observation) == ("identity_service", "ACCOUNT_TOMBSTONE", "PRESENT")
    assert t1.pii_fields == {"name", "email", "phone", "email_hash"}
    assert t2.observation == "REDACTED" and t2.pii_fields == frozenset() and dict(t2.subject_keys) == {"user_id": "user_6"}
    assert one(facts, "legal_hold_1").category == "LEGAL_HOLD_RECORD"
    assert {c.system_id for c in cov} == {"support_platform", "identity_service", "legal_service"}


def test_flow_backup_export_snapshots(tmp_path):
    doc = bundle(
        ("integration_service", "connector_configurations", [
            {"resource_id": "data_flow_1", "connector_name": "c", "destination": "d", "mode": "continuous_sync",
             "enabled": True, "subject_selector": "user_8"},
            {"resource_id": "data_flow_2", "connector_name": "c", "destination": "d", "mode": "continuous_sync",
             "enabled": False, "subject_selector": "S@EXAMPLE.com"}]),
        ("backup_service", "backup_catalog", [
            {"resource_id": "backup_1", "archive_path": "p", "encryption": "e", "restore_allowed": True, "subject_reference": "user_8"},
            {"resource_id": "backup_2", "archive_path": "p", "encryption": "e", "restore_allowed": False, "subject_reference": "user_8"}]),
        ("export_service", "customer_export_jobs", [
            {"resource_id": "export_1", "created_at": "c", "expires_at": "e", "file_name": "f", "included_sections": [],
             "download_available": True, "owner_email": "O@example.com"},
            {"resource_id": "export_2", "created_at": "c", "expires_at": "e", "file_name": "f", "included_sections": [],
             "download_available": False, "owner_email": "o@example.com"}]))
    facts, _ = run(tmp_path, doc)
    assert [one(facts, r).observation for r in ("data_flow_1", "data_flow_2")] == ["FLOW_ACTIVE", "FLOW_DISABLED"]
    assert one(facts, "data_flow_1").category == "DATA_FLOW" and one(facts, "data_flow_1").system_id == "integration_service"
    assert dict(one(facts, "data_flow_2").subject_keys) == {"email": "s@example.com"}
    assert [one(facts, r).observation for r in ("backup_1", "backup_2")] == ["RESTORE_OPEN", "RESTORE_BLOCKED"]
    assert [one(facts, r).observation for r in ("export_1", "export_2")] == ["PRESENT", "ABSENT"]
    assert one(facts, "export_1").category == "USER_EXPORT"
    assert dict(one(facts, "export_1").subject_keys) == {"email": "o@example.com"}


def test_service_export_shapes_use_row_time_and_never_cover(tmp_path):
    exp = {"exported_at": "x", "region": "r", "source": "t", "service_exports": {
        "account_service": {"profile_lookups": [
            {"resource_id": "account_1", "status_code": 200, "observed_at": "2026-09-05T00:00:00Z",
             "profile": {"customer_reference": None, "email": "P@Example.com", "email_hash": None, "full_name": None, "phone": None}},
            {"resource_id": "account_2", "status_code": 404, "observed_at": "2026-09-06T00:00:00Z", "profile": None}]},
        "search_service": {"index_queries": [
            {"resource_id": "search_1", "observed_at": "2026-09-05T00:00:00Z", "query": "Q@EXAMPLE.com",
             "hits": {"total": 1, "documents": [{"resource_id": "search_1", "display_name": None, "email": "q@example.com",
                                                  "customer_reference": None, "email_hash": None, "phone": None}]}},
            {"resource_id": "search_2", "observed_at": "2026-09-05T00:00:00Z", "query": "r@example.com",
             "hits": {"total": 0, "documents": []}}]},
        "support_platform": {"tickets": [
            {"resource_id": "support_1", "observed_at": "2026-09-05T00:00:00Z", "customer_reference": None,
             "message_excerpt": "m", "requester_email": "T@example.com", "requester_name": None, "requester_phone": None},
            {"resource_id": "support_2", "observed_at": "2026-09-05T00:00:00Z", "customer_reference": "user_1",
             "message_excerpt": "m", "requester_email": None, "requester_name": None, "requester_phone": None}]},
        "analytics_platform": {"profiles": [
            {"resource_id": "analytics_1", "observed_at": "2026-09-05T00:00:00Z", "audience_cohort": "a", "customer_reference": None,
             "email": None, "email_hash": None, "phone": None}]},
        "backup_service": {"restore_entries": [
            {"resource_id": "backup_1", "observed_at": "2026-09-05T00:00:00Z", "archive_key": "k", "customer_email": None,
             "customer_reference": "user_1", "restore_allowed": True}]},
        "export_service": {"exports": [
            {"resource_id": "export_1", "observed_at": "2026-09-05T00:00:00Z", "object_key": "k", "owner_email": "e@example.com",
             "owner_phone": None, "customer_reference": None}]},
        "integration_service": {"connectors": [
            {"resource_id": "data_flow_1", "observed_at": "2026-09-05T00:00:00Z", "connector_name": "c", "enabled": False,
             "last_delivery_status": "stopped", "customer_email": None, "customer_reference": "user_1"}]},
        "security_service": {"audit_records": [
            {"resource_id": "audit_record_1", "observed_at": "2026-09-05T00:00:00Z", "event_code": "e",
             "retention_until": "2032-01-01T00:00:00Z", "subject_reference": "user_1"}]}}}
    facts, cov = run(tmp_path, exp)
    assert cov == []
    a1, a2 = one(facts, "account_1"), one(facts, "account_2")
    assert (a1.observation, a1.observed_at, dict(a1.subject_keys)) == ("PRESENT", "2026-09-05T00:00:00Z", {"email": "p@example.com"})
    assert (a2.observation, a2.subject_keys, a2.category) == ("ABSENT", (), "USER_PROFILE")
    assert one(facts, "search_1").observation == "PRESENT" and dict(one(facts, "search_1").subject_keys) == {"email": "q@example.com"}
    assert one(facts, "search_2").observation == "ABSENT"
    t1, t2 = one(facts, "support_1"), one(facts, "support_2")
    assert t1.observation == "PRESENT" and t1.pii_fields == {"email"}
    assert t2.observation == "REDACTED" and dict(t2.subject_keys) == {"user_id": "user_1"}
    assert one(facts, "analytics_1").observation == "ANONYMIZED"
    assert one(facts, "backup_1").observation == "RESTORE_OPEN" and dict(one(facts, "backup_1").subject_keys) == {"user_id": "user_1"}
    assert one(facts, "export_1").observation == "PRESENT"
    assert one(facts, "data_flow_1").observation == "FLOW_DISABLED"
    assert one(facts, "audit_record_1").category == "SECURITY_AUDIT_LOG"
    assert one(facts, "audit_record_1").system_id == "security_service"


def test_flat_collection_files_use_top_captured_at(tmp_path):
    doc = {"captured_at": "2026-08-20T00:00:00Z", "collection": "customer_export_jobs", "source": "s", "records": [
        {"resource_id": "export_1", "created_at": "c", "expires_at": "e", "file_name": "f", "included_sections": [],
         "download_available": True, "owner_email": "o@example.com"}]}
    facts, cov = run(tmp_path, doc)
    assert cov == [] and one(facts, "export_1").observed_at == "2026-08-20T00:00:00Z"
    doc = {"captured_at": "2026-08-20T00:00:00Z", "collection": "customer_analytics_reports", "source": "s", "records": [
        {"resource_id": "analytics_1", "user_id": None, "email": None, "phone": None, "email_hash": None,
         "reporting_window": "w", "metrics": {}, "recent_activity": []}]}
    facts, cov = run(tmp_path, doc)
    assert cov == [] and one(facts, "analytics_1").observation == "ANONYMIZED"


def test_malformed_raises(tmp_path):
    with pytest.raises(Exception):
        run(tmp_path, {"unknown": 1})
    p = tmp_path / "bad.json"
    p.write_text("{nope", encoding="utf-8")
    with pytest.raises(Exception):
        ev_json.parse(p, META)


def test_real_json_files_all_parse():
    from ghost import evidence as ev
    from ghost.safety import safe_evidence_path
    manifest = [m for m in csv.DictReader(open(DATASET / "evidence_files.csv", encoding="utf-8")) if m["file_path"].endswith(".json")]
    assert len(manifest) == 28
    total = 0
    for m in manifest:
        facts, cov = ev_json.parse(safe_evidence_path(m["file_path"]), m)
        assert facts, m["file_id"]
        assert all(isinstance(f, ev.Fact) for f in facts)
        total += len(facts)
    assert total == 890  # one Fact per source record (profiled 2026-10-25)
    facts, _, quarantined = ev.ingest(_Trail(), manifest)
    assert quarantined == [] and len([f for f in facts if f.evidence_kind == "FILE" and f.evidence_id in {m["file_id"] for m in manifest}]) == total


class _Trail:
    def event(self, *a, **k):
        pass
