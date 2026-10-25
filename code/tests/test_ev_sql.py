"""P1-05a: SQL evidence parser. Behaviour tests use synthetic fixtures; real files only for counts and ids."""
import csv

import pytest

from ghost import contract, evidence as ev, ev_sql
from ghost.safety import safe_evidence_path

META = {"file_id": "evidence_x", "captured_at": "2026-09-01T00:00:00Z"}
HASH = "ab" * 32

INVENTORY = f"""-- header
BEGIN TRANSACTION;
CREATE TABLE snapshot_scope (origin_system TEXT PRIMARY KEY, captured_at TEXT NOT NULL);
INSERT INTO snapshot_scope VALUES('account_service','2026-08-30T10:00:00Z');
INSERT INTO snapshot_scope VALUES('search_service','2026-08-30T10:00:00Z');
INSERT INTO snapshot_scope VALUES('analytics_platform','2026-08-30T10:00:00Z');
INSERT INTO snapshot_scope VALUES('support_platform','2026-08-30T10:00:00Z');
INSERT INTO snapshot_scope VALUES('export_service','2026-08-30T10:00:00Z');
INSERT INTO snapshot_scope VALUES('integration_service','2026-08-30T10:00:00Z');
INSERT INTO snapshot_scope VALUES('security_service','2026-08-30T10:00:00Z');
CREATE TABLE customer_profiles (resource_id TEXT PRIMARY KEY, customer_reference TEXT, full_name TEXT, email TEXT, phone TEXT, email_hash TEXT, account_status TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO customer_profiles VALUES('account_1','user_1','Test One','Jane.Doe@EXAMPLE.com','+1 (555) 010-0001','{HASH.upper()}','ACTIVE','2026-08-29T01:00:00Z');
INSERT INTO customer_profiles VALUES('account_2','user_2','NULL','[REDACTED]',NULL,'','DELETION_PENDING','');
CREATE TABLE customer_search_documents (resource_id TEXT PRIMARY KEY, customer_reference TEXT, display_name TEXT, email TEXT, phone TEXT, email_hash TEXT, index_name TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO customer_search_documents VALUES('search_1','user_1','Test One','a@example.com',NULL,NULL,'idx','2026-08-29T01:00:00Z');
CREATE TABLE customer_analytics_profiles (resource_id TEXT PRIMARY KEY, customer_reference TEXT, email TEXT, phone TEXT, email_hash TEXT, audience_cohort TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO customer_analytics_profiles VALUES('analytics_1',NULL,NULL,NULL,NULL,'c','2026-08-29T01:00:00Z');
INSERT INTO customer_analytics_profiles VALUES('analytics_2',NULL,'b@example.com',NULL,NULL,'c','2026-08-29T01:00:00Z');
CREATE TABLE support_records (resource_id TEXT PRIMARY KEY, customer_reference TEXT, requester_name TEXT, requester_email TEXT, requester_phone TEXT, message_excerpt TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO support_records VALUES('support_1',NULL,NULL,'c@example.com',NULL,'hi','2026-08-29T01:00:00Z');
INSERT INTO support_records VALUES('support_2','user_2',NULL,NULL,NULL,'hi','2026-08-29T01:00:00Z');
CREATE TABLE customer_exports (resource_id TEXT PRIMARY KEY, customer_reference TEXT, owner_email TEXT, owner_phone TEXT, object_key TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE connector_subscriptions (resource_id TEXT PRIMARY KEY, customer_reference TEXT, customer_email TEXT, connector_name TEXT NOT NULL, enabled INTEGER NOT NULL, last_delivery_status TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO connector_subscriptions VALUES('data_flow_1',NULL,'d@example.com','c',1,'delivered','2026-08-29T01:00:00Z');
INSERT INTO connector_subscriptions VALUES('data_flow_2','user_2',NULL,'c','0','stopped','2026-08-29T01:00:00Z');
CREATE TABLE backup_restore_entries (resource_id TEXT PRIMARY KEY, customer_reference TEXT, customer_email TEXT, archive_key TEXT NOT NULL, restore_allowed INTEGER NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO backup_restore_entries VALUES('backup_1',NULL,'e@example.com','k','1','2026-08-29T01:00:00Z');
INSERT INTO backup_restore_entries VALUES('backup_2','user_2',NULL,'k',0,'2026-08-29T01:00:00Z');
CREATE TABLE security_audit_records (resource_id TEXT PRIMARY KEY, subject_reference TEXT NOT NULL, event_code TEXT NOT NULL, retention_until TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO security_audit_records VALUES('audit_record_1','user_1','E','2032-01-01T00:00:00Z','2026-08-29T01:00:00Z');
COMMIT;
-- snapshot_completed_at=2026-08-30T10:00:00Z
"""

GENERIC = """-- Captured at: 2026-09-02T12:00:00Z
CREATE TABLE customer_data_primary (resource_id TEXT PRIMARY KEY, origin_system TEXT NOT NULL, collection_name TEXT NOT NULL, record_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE customer_data_read_replica (resource_id TEXT PRIMARY KEY, origin_system TEXT NOT NULL, collection_name TEXT NOT NULL, record_json TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO customer_data_primary VALUES('search_9','search_service','customer_search_documents','{"document":{"display_name":"X","email":"S@Example.com","customer_reference":"user_9"}}','2026-09-01T00:00:00Z');
INSERT INTO customer_data_primary VALUES('tombstone_1','identity_service','deleted_customer_references','{"name":null,"email":null,"phone":null,"email_hash":null,"subject_reference":"user_3","account_status":"DELETED"}','2026-09-01T00:00:00Z');
INSERT INTO customer_data_primary VALUES('tombstone_2','identity_service','deleted_customer_references','{"name":"N","email":"t@example.com","phone":"+44 20 7946 0000","email_hash":null,"subject_reference":"user_4","account_status":"DELETED"}','');
INSERT INTO customer_data_primary VALUES('data_flow_9','integration_service','connector_configurations','{"subject_selector":"f@example.com","enabled":false,"mode":"continuous_sync"}','2026-09-01T00:00:00Z');
INSERT INTO customer_data_primary VALUES('backup_9','backup_service','backup_catalog','{"subject_reference":"user_5","restore_allowed":true}','2026-09-01T00:00:00Z');
INSERT INTO customer_data_primary VALUES('audit_record_9','security_service','security_audit_events','{"subject_reference":"user_5","event_name":"x"}','2026-09-01T00:00:00Z');
INSERT INTO customer_data_primary VALUES('support_9','support_platform','ticket_attachments','{"uploaded_by":"G@example.com","file_name":"a.pdf"}','2026-09-01T00:00:00Z');
INSERT INTO customer_data_read_replica SELECT * FROM customer_data_primary;
INSERT INTO customer_data_read_replica VALUES('account_77','account_service','customer_profiles','{"customer_reference":"user_7","email":"h@example.com","full_name":"Z","phone":null,"account_status":"ACTIVE"}','2026-09-01T00:00:00Z');
"""

ACCOUNTS = """-- Captured at: 2026-09-02T23:00:00Z
CREATE TABLE customer_profiles_primary (resource_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, account_status TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE customer_profiles_failover_replica (resource_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, account_status TEXT NOT NULL, updated_at TEXT NOT NULL);
INSERT INTO customer_profiles_primary VALUES('account_8','user_8','A','a@example.com','+1 555 0100','ACTIVE','2026-09-02T22:45:00Z');
INSERT INTO customer_profiles_failover_replica VALUES('account_8','user_8','A','a@example.com','+1 555 0100','ACTIVE','2026-09-02T22:45:00Z');
INSERT INTO customer_profiles_failover_replica VALUES('account_5','user_5','B','b@example.com','+1 555 0101','ACTIVE','2026-09-02T22:45:00Z');
"""

SEARCH = """-- Captured at: 2026-09-10T08:45:00Z
CREATE TABLE search_documents_primary (resource_id TEXT PRIMARY KEY, display_name TEXT, email TEXT, source_resource_id TEXT, indexed_at TEXT);
INSERT INTO search_documents_primary VALUES('search_1','N','S@Example.com','account_6','2026-09-09T22:12:00Z');
"""

EMPTY_SCOPE_ONLY = """CREATE TABLE snapshot_scope (origin_system TEXT PRIMARY KEY, captured_at TEXT NOT NULL);
INSERT INTO snapshot_scope VALUES('account_service','2026-09-05T07:18:01Z');
CREATE TABLE customer_profiles (resource_id TEXT PRIMARY KEY, customer_reference TEXT, full_name TEXT, email TEXT, phone TEXT, email_hash TEXT, account_status TEXT NOT NULL, updated_at TEXT NOT NULL);
"""


def run(tmp_path, sql):
    p = tmp_path / "f.sql"
    p.write_text(sql, encoding="utf-8")
    return ev_sql.parse(p, META)


def by_res(facts):
    return {f.resource_id: f for f in facts}


def test_inventory_observation_kinds(tmp_path):
    facts, _ = run(tmp_path, INVENTORY)
    f = by_res(facts)
    assert f["account_1"].observation == "PRESENT" and f["account_1"].system_id == "account_service"
    assert f["account_1"].category == "USER_PROFILE" and f["account_1"].evidence_kind == "FILE"
    assert f["account_1"].evidence_id == "evidence_x" and f["account_1"].captured_at == META["captured_at"]
    assert f["search_1"].category == "SEARCH_INDEX_ENTRY" and f["search_1"].observation == "PRESENT"
    assert f["analytics_1"].observation == "ANONYMIZED" and f["analytics_1"].pii_fields == frozenset()
    assert f["analytics_2"].observation == "PRESENT" and f["analytics_2"].pii_fields == {"email"}
    assert f["support_1"].observation == "PRESENT" and f["support_1"].pii_fields == {"email"}
    assert f["support_1"].category == "SUPPORT_MESSAGE"
    assert f["support_2"].observation == "REDACTED" and f["support_2"].pii_fields == frozenset()
    assert f["support_2"].subject_keys == (("user_id", "user_2"),)
    assert f["data_flow_1"].observation == "FLOW_ACTIVE" and f["data_flow_1"].category == "DATA_FLOW"
    assert f["data_flow_1"].system_id == "integration_service"
    assert f["data_flow_2"].observation == "FLOW_DISABLED"  # string '0'
    assert f["backup_1"].observation == "RESTORE_OPEN" and f["backup_1"].category == "BACKUP_ARCHIVE"
    assert f["backup_2"].observation == "RESTORE_BLOCKED"
    assert f["audit_record_1"].category == "SECURITY_AUDIT_LOG" and f["audit_record_1"].system_id == "security_service"
    assert f["audit_record_1"].subject_keys == (("user_id", "user_1"),)


def test_keys_lowercase_nulls_and_time_precedence(tmp_path):
    facts, _ = run(tmp_path, INVENTORY)
    f = by_res(facts)
    assert f["account_1"].subject_keys == (("email", "jane.doe@example.com"), ("email_hash", HASH),
                                           ("name", "Test One"), ("phone", "15550100001"), ("user_id", "user_1"))
    assert f["account_1"].observed_at == "2026-08-29T01:00:00Z"  # row updated_at
    # null tokens ("NULL", "[REDACTED]", "") are dropped; blank updated_at falls back to the scope time
    assert f["account_2"].subject_keys == (("user_id", "user_2"),)
    assert f["account_2"].observed_at == "2026-08-30T10:00:00Z"


def test_inventory_coverage_follows_scope_and_counts_empty_tables(tmp_path):
    _, cov = run(tmp_path, INVENTORY)
    systems = {c.system_id for c in cov}
    assert systems == {"account_service", "search_service", "analytics_platform", "support_platform",
                       "export_service", "integration_service", "security_service"}  # export table is empty
    assert all(isinstance(c, ev.Coverage) and c.evidence_id == "evidence_x" for c in cov)
    assert all(c.observed_at == "2026-08-30T10:00:00Z" for c in cov)
    assert len(cov) == len(systems)  # backup_service not in scope -> none


def test_file_without_data_rows_proves_nothing(tmp_path):
    facts, cov = run(tmp_path, EMPTY_SCOPE_ONLY)
    assert facts == [] and cov == []


def test_generic_replica_rows_stay_on_primary_system(tmp_path):
    facts, cov = run(tmp_path, GENERIC)
    f = by_res(facts)
    assert f["account_77"].system_id == "account_service" and f["account_77"].observation == "PRESENT"
    assert f["account_77"].subject_keys == (("email", "h@example.com"), ("name", "Z"), ("user_id", "user_7"))
    assert f["search_9"].subject_keys == (("email", "s@example.com"), ("name", "X"), ("user_id", "user_9"))
    assert f["tombstone_1"].observation == "REDACTED" and f["tombstone_1"].category == "ACCOUNT_TOMBSTONE"
    assert f["tombstone_1"].system_id == "identity_service" and f["tombstone_1"].pii_fields == frozenset()
    assert f["tombstone_2"].observation == "PRESENT" and f["tombstone_2"].pii_fields == {"email", "name", "phone"}
    assert f["tombstone_2"].observed_at == "2026-09-02T12:00:00Z"  # header Captured at
    assert f["data_flow_9"].observation == "FLOW_DISABLED" and f["data_flow_9"].subject_keys == (("email", "f@example.com"),)
    assert f["backup_9"].observation == "RESTORE_OPEN"
    assert f["support_9"].category == "SUPPORT_ATTACHMENT" and f["support_9"].subject_keys == (("email", "g@example.com"),)
    # primary rows duplicated in the replica collapse to one fact
    assert len([x for x in facts if x.resource_id == "search_9"]) == 1
    # coverage = systems of the primary table only; the replica-only account row is drift, not coverage
    assert {c.system_id for c in cov} == {"search_service", "identity_service", "integration_service",
                                          "backup_service", "security_service", "support_platform"}


def test_accounts_failover_and_search_primary(tmp_path):
    facts, cov = run(tmp_path, ACCOUNTS)
    f = by_res(facts)
    assert f["account_5"].system_id == "account_service" and f["account_5"].observation == "PRESENT"
    assert ("user_id", "user_5") in f["account_5"].subject_keys
    assert [c.system_id for c in cov] == ["account_service"]
    facts, cov = run(tmp_path, SEARCH)
    s = facts[0]
    assert (s.system_id, s.category, s.observation) == ("search_service", "SEARCH_INDEX_ENTRY", "PRESENT")
    assert s.observed_at == "2026-09-09T22:12:00Z" and ("email", "s@example.com") in s.subject_keys
    assert [c.system_id for c in cov] == ["search_service"]


def test_sorted_and_deterministic(tmp_path):
    facts, cov = run(tmp_path, INVENTORY)
    key = lambda f: (f.evidence_id, f.system_id, f.resource_id, f.observation)
    assert facts == sorted(facts, key=key)
    assert run(tmp_path, INVENTORY) == (facts, cov)


def test_unknown_table_or_bad_flag_raises(tmp_path):
    with pytest.raises(Exception):
        run(tmp_path, "CREATE TABLE mystery (a TEXT); INSERT INTO mystery VALUES('x');")
    with pytest.raises(Exception):
        run(tmp_path, "CREATE TABLE not sql")


# ---- real dataset: counts and ids only ----

def sql_manifest():
    rows = csv.DictReader(open(contract.DATASET / "evidence_files.csv", encoding="utf-8"))
    return [r for r in rows if r["file_path"].endswith(".sql")]


class _Trail:
    def event(self, *a, **k):
        pass


def test_all_real_sql_files_parse_without_quarantine():
    manifest = sql_manifest()
    assert len(manifest) == 24
    facts, cov, quarantined = ev.ingest(_Trail(), manifest=manifest)
    assert quarantined == []
    assert {f.evidence_id for f in facts} <= {m["file_id"] for m in manifest}
    assert len(facts) > 500 and len(cov) > 20


def test_real_replica_only_account_is_present_in_evidence_54():
    m = next(r for r in sql_manifest() if r["file_id"] == "evidence_54")
    facts, cov = ev_sql.parse(safe_evidence_path(m["file_path"]), m)
    hits = [f for f in facts if f.resource_id == "account_005"]
    assert len(hits) == 1 and hits[0].system_id == "account_service" and hits[0].observation == "PRESENT"
    assert [c.system_id for c in cov] == ["account_service"]
