import pytest

from ghost import evidence as ev


def test_system_from_prefix_and_explicit_wins():
    assert ev.system_for("account_123") == "account_service"
    assert ev.system_for("data_flow_7") == "integration_service"
    assert ev.system_for("audit_record_9") == "security_service"
    assert ev.system_for("account_123", explicit="backup_service") == "backup_service"
    assert ev.system_for("weird_1") is None


@pytest.mark.parametrize("v", [None, "", "null", "NULL", "None", "[REDACTED]", "  "])
def test_null_tokens(v):
    assert ev.is_null(v)


def test_norm_keys_normalizes_and_drops_nulls():
    keys = ev.norm_keys({"email": " Jane.Doe@Example.COM ", "user_id": "user_5", "phone": "+1 (555) 010-2016",
                         "email_hash": "AB" * 32, "name": "Jane Doe", "extra": "x", "customer_email": "null"})
    assert keys == (("email", "jane.doe@example.com"), ("email_hash", "ab" * 32), ("name", "Jane Doe"),
                    ("phone", "15550102016"), ("user_id", "user_5"))


def test_fact_and_coverage_contract():
    f = ev.Fact(evidence_id="evidence_1", evidence_kind="FILE", captured_at="2026-09-01T00:00:00Z",
                observed_at="2026-08-31T00:00:00Z", system_id="account_service", resource_id="account_1",
                category="USER_PROFILE", observation="PRESENT", subject_keys=(("user_id", "user_5"),))
    assert f.pii_fields == frozenset() and f.is_claim is False
    c = ev.Coverage("evidence_1", "account_service", "2026-09-01T00:00:00Z", "2026-08-31T00:00:00Z")
    assert c.system_id == "account_service"


def fake_manifest(*paths):
    return [{"file_id": f"evidence_{i}", "file_path": p, "origin": "x", "captured_at": "2026-09-01T00:00:00Z"}
            for i, p in enumerate(paths, 1)]


class Trail:
    def __init__(self):
        self.events = []

    def event(self, stage, summary, **kw):
        self.events.append((stage, summary, kw))


def test_ingest_dispatches_by_suffix_and_quarantines_failures():
    seen = []

    def ok(path, meta):
        seen.append(meta["file_id"])
        return [ev.Fact(meta["file_id"], "FILE", meta["captured_at"], meta["captured_at"], "account_service",
                        "account_1", "USER_PROFILE", "PRESENT")], []

    def boom(path, meta):
        raise ValueError("bad row")

    manifest = fake_manifest("evidence/logs/support_replica.log",
                             "evidence/databases/customer_data_inventory_20260916.sql",
                             "evidence/images/backup_restore_console_20260429.png",
                             "evidence/../../AGENTS.md")
    t = Trail()
    facts, coverage, quarantined = ev.ingest(t, manifest=manifest, parsers={".log": ok, ".sql": boom})
    assert seen == ["evidence_1"] and len(facts) == 1 and coverage == []
    assert [q for q, _ in quarantined] == ["evidence_2", "evidence_4"]           # parser error + unsafe path
    assert any("deferred" in s for _, s, _ in t.events)                          # png waits for P2-02


def test_real_manifest_ingests_without_quarantine_using_stub_parsers():
    facts, coverage, quarantined = ev.ingest(Trail())
    assert quarantined == []
