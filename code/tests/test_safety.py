import sqlite3

import pytest

from ghost import safety


# T5 path traversal
def test_manifest_path_inside_evidence_ok():
    p = safety.safe_evidence_path("evidence/logs/support_replica.log")
    assert p.is_file()


@pytest.mark.parametrize("bad", ["../README.md", "evidence/../../AGENTS.md", "/etc/passwd", "C:/Windows/win.ini",
                                 "deletion_rules.csv", "evidence/logs/does_not_exist.log"])
def test_manifest_path_outside_or_missing_rejected(bad):
    with pytest.raises(safety.UnsafeInput):
        safety.safe_evidence_path(bad)


def test_oversized_file_rejected(monkeypatch):
    monkeypatch.setattr(safety, "MAX_FILE_BYTES", 10)
    with pytest.raises(safety.UnsafeInput):
        safety.safe_evidence_path("evidence/logs/support_replica.log")


# T4 malicious SQL dumps
def test_sandboxed_sqlite_loads_normal_dump():
    conn = safety.open_sandboxed_sqlite(
        "PRAGMA foreign_keys=ON; BEGIN TRANSACTION; CREATE TABLE t (a TEXT); INSERT INTO t VALUES ('x'); COMMIT;")
    assert conn.execute("SELECT a FROM t").fetchall() == [("x",)]


def test_real_snapshot_loads():
    path = safety.safe_evidence_path("evidence/databases/customer_data_inventory_20260916.sql")
    conn = safety.open_sandboxed_sqlite(path.read_text(encoding="utf-8"))
    assert conn.execute("SELECT count(*) FROM customer_profiles").fetchone()[0] > 0


@pytest.mark.parametrize("evil", [
    "ATTACH DATABASE 'pwned.db' AS p;",
    "PRAGMA writable_schema=ON;",
    "SELECT load_extension('evil');",
    "CREATE TABLE t (a); VACUUM INTO 'pwned.db';",
])
def test_sandboxed_sqlite_denies_escape(evil, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(sqlite3.DatabaseError):
        safety.open_sandboxed_sqlite(evil)
    assert not (tmp_path / "pwned.db").exists()


def test_sandboxed_sqlite_aborts_runaway_query(monkeypatch):
    monkeypatch.setattr(safety, "SQL_MAX_STEPS", 10_000)
    with pytest.raises(sqlite3.DatabaseError):
        safety.open_sandboxed_sqlite(
            "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r) SELECT count(*) FROM r;")


# T9 PII masking in human-readable trails
def test_mask_email_phone_hash():
    assert safety.mask("jane.doe@example.com") == "j***@example.com"
    assert safety.mask("+1 555 010 2016") == "***16"
    assert safety.mask("d4e1f50000000000000000000000000000000000000000000000000000000000") == "d4e1f5…"
    assert safety.mask("account_005") == "account_005"  # resource ids stay readable


def test_mask_text_scrubs_free_text():
    s = safety.mask_text("lookup_key=sam.lee@example.org phone=+44 7700 900123 resource_id=support_002")
    assert "sam.lee" not in s and "7700 900" not in s and "support_002" in s


def test_mask_text_keeps_timestamps_and_counts():
    s = "observed 2026-09-17T22:00:05Z rows=1 latency_ms=18 trace=rb-044751-001"
    assert safety.mask_text(s) == s
