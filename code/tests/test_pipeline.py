import json

import pytest

from ghost import contract as c
from ghost import pipeline

SAMPLE = c.DATASET / "sample_deletion_requests.csv"


@pytest.fixture
def run(tmp_path):
    def _run(name="out.csv", **kw):
        out = tmp_path / name
        manifest = pipeline.run(SAMPLE, out, runs_dir=tmp_path / "runs", offline=True, **kw)
        return out, manifest
    return _run


def test_sample_run_is_contract_valid(run):
    out, manifest = run()
    assert c.validate_output(out, SAMPLE) == []
    assert manifest["cases"] == 32 and manifest["g6_failures"] == 0


def test_run_writes_readable_trail(run, tmp_path):
    _, manifest = run()
    d = tmp_path / "runs" / manifest["run_id"]
    assert {"trail.jsonl", "report.md", "manifest.json"} <= {p.name for p in d.iterdir()}
    events = [json.loads(x) for x in (d / "trail.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {e["gate"] for e in events} >= {"G1", "G2", "G3", "G7"}
    assert sum(e["stage"] == "emit" for e in events) == 32


def test_manifest_records_input_and_output_hashes(run):
    _, m = run()
    assert len(m["output_sha256"]) == 64 and len(m["inputs"]["sample_deletion_requests.csv"]) == 64


def test_rerun_is_byte_identical(run):
    a, ma = run("a.csv")
    b, mb = run("b.csv")
    assert a.read_bytes() == b.read_bytes() and ma["output_sha256"] == mb["output_sha256"]


def test_case_filter(run):
    out, m = run(cases=["case_03", "case_01"])
    assert [r["case_id"] for r in c.read_csv(out)] == ["case_01", "case_03"] and m["cases"] == 2


def test_bad_input_aborts_at_g1(tmp_path):
    bad = tmp_path / "req.csv"
    bad.write_text("case_id,email\ncase_1,x@y.z\n", encoding="utf-8")
    with pytest.raises(pipeline.GateFailure, match="G1"):
        pipeline.run(bad, tmp_path / "o.csv", runs_dir=tmp_path / "runs", offline=True)


def test_unplannable_case_degrades_safely(run, monkeypatch, tmp_path):
    from ghost import intent, planner
    monkeypatch.setattr(intent, "classify", lambda text, offline=True, client=None: intent.Intent("DELETE", 0.9, "test"))
    monkeypatch.setattr(planner, "plan", lambda verdicts: (_ for _ in ()).throw(ValueError("no verdicts")))
    out, m = run()                                   # an unplannable case must not abort the run
    assert c.validate_output(out, SAMPLE) == [] and m["g6_failures"] == 0
    events = [json.loads(x) for x in (tmp_path / "runs" / m["run_id"] / "trail.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["stage"] == "plan" and e["verdict"] == "WARN" and "could not plan" in e["summary"] for e in events)
