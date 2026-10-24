import json
import re

from ghost import audit


def make_trail(tmp_path):
    t = audit.Trail(tmp_path, "20261024T180000Z-abc123")
    t.event("load", "Loaded 2 requests.", gate="G1", verdict="PASS")
    t.event("intent", "Request asks to delete the account of sam.lee@example.org.", case_id="case_2",
            gate="G3", verdict="PASS", detail={"lookup": "sam.lee@example.org"})
    t.event("identity", "Email matched no identity.", case_id="case_2", gate="G4", verdict="WARN")
    t.event("emit", "Audited INCOMPLETE: 1 finding.", case_id="case_2", evidence_ids=["evidence_54"],
            detail={"reported": "COMPLETE", "status": "INCOMPLETE", "steps": 3})
    t.event("emit", "Audited NOT_APPLICABLE.", case_id="case_10",
            detail={"reported": "NOT_STARTED", "status": "NOT_APPLICABLE", "steps": 0})
    return t


def test_new_run_id_format():
    assert re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}", audit.new_run_id())


def test_events_are_jsonl_with_schema_and_masked(tmp_path):
    t = make_trail(tmp_path)
    lines = (tmp_path / t.run_id / "trail.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(x) for x in lines]
    assert len(events) == 5
    assert set(events[1]) == {"ts", "run_id", "case_id", "stage", "gate", "verdict", "summary", "evidence_ids", "detail"}
    raw = "\n".join(lines)
    assert "sam.lee" not in raw and "s***@example.org" in raw


def test_close_writes_manifest_and_readable_report(tmp_path):
    t = make_trail(tmp_path)
    report = t.close({"run_id": t.run_id, "output_sha256": "f" * 64, "cases": 2})
    run = tmp_path / t.run_id
    assert json.loads((run / "manifest.json").read_text(encoding="utf-8"))["cases"] == 2
    md = (run / "report.md").read_text(encoding="utf-8")
    assert md == report
    assert md.startswith("# Audit run 20261024T180000Z-abc123")
    assert "| G4 | 0 | 1 | 0 |" in md                       # gate summary: PASS WARN FAIL
    assert "| COMPLETE | INCOMPLETE |" in md or "COMPLETE → INCOMPLETE" in md  # claim vs truth
    assert "case_2" in md and "Email matched no identity." in md  # non-PASS cases get detail
    assert "sam.lee" not in md


def test_cases_listed_in_numeric_order(tmp_path):
    md = make_trail(tmp_path).close({"run_id": "x"})
    assert md.index("case_2") < md.index("case_10")
