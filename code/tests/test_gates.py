import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts" / "gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_secret_scan_flags_keys_not_prose(tmp_path):
    bad = write(tmp_path, "a.py", 'KEY = "nvapi-' + "x" * 40 + '"\n')
    ok = write(tmp_path, "b.md", "Set NVIDIA_API_KEY in .env; never commit it.\n")
    pem = write(tmp_path, "c.txt", "-----BEGIN " + "RSA PRIVATE KEY-----\n")
    hits = gate.scan_secrets([bad, ok, pem], tmp_path)
    assert {h.split(":")[0] for h in hits} == {"a.py", "c.txt"}


def test_unsafe_api_scan(tmp_path):
    bad = write(tmp_path, "code/x.py", "import subprocess\nsubprocess.run(cmd, shell" + "=True)\n")
    ok = write(tmp_path, "code/y.py", "subprocess.run(['git', 'status'])\n")
    assert [h.split(":")[0] for h in gate.scan_unsafe([bad, ok], tmp_path)] == ["code/x.py"]


def test_golden_leak_scan_allows_only_evaluation(tmp_path):
    leak = write(tmp_path, "code/ghost/p.py", "open('dataset/sample_" + "output.csv')\n")
    allowed = write(tmp_path, "code/evaluation/main.py", "DATASET / 'sample_" + "output.csv'\n")
    test = write(tmp_path, "code/tests/t.py", "'sample_" + "output.csv'\n")
    assert gate.scan_golden_leak([leak, allowed, test], tmp_path) == ["code/ghost/p.py"]


def test_pii_scan_finds_dataset_emails(tmp_path):
    f = write(tmp_path, "log.txt", "user asked about someone@example.org\n")
    assert gate.scan_pii([f], tmp_path, {"someone@example.org"}) == ["log.txt: someone@example.org"]


def test_gate_log_append_and_parse_eval_baseline(tmp_path):
    log = tmp_path / "gate_log.md"
    gate.append_log(log, "eval", "PASS", "status=0.500 step_f1=0.250 field=0.300 seq=0.100 (32 cases)")
    gate.append_log(log, "eval", "FAIL", "status=0.100 step_f1=0.100 field=0.100 seq=0.000 (32 cases)")
    text = log.read_text(encoding="utf-8")
    assert text.startswith("# Dev gate log") and text.count("| eval |") == 2
    assert gate.last_eval_baseline(log) == {"status": 0.5, "step_f1": 0.25, "field": 0.3, "seq": 0.1}


def test_regressions():
    prev = {"status": 0.5, "step_f1": 0.25, "field": 0.3, "seq": 0.1}
    assert gate.regressions(prev, {**prev, "seq": 0.2}) == []
    assert gate.regressions(prev, {**prev, "status": 0.4}) == ["status 0.500 -> 0.400"]
    assert gate.regressions(None, prev) == []


def test_package_allowlist_excludes_junk(tmp_path):
    for rel in ["code/main.py", "code/README.md", "code/evaluation/evaluation_report.md",
                "code/__pycache__/x.pyc", "code/.env", "code/nested.zip", "dataset/x.csv"]:
        write(tmp_path, rel, "x")
    names = sorted(gate.package_members(tmp_path))
    assert names == ["README.md", "evaluation/evaluation_report.md", "main.py"]


def test_required_local_paths_are_gitignored():
    assert gate.unignored(ROOT) == []


def test_unignored_flags_missing_entries(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    missing = gate.unignored(tmp_path)
    assert ".env" not in missing and ".claude/worktrees/" in missing and "runs/" in missing


def test_identical_bytes_helper(tmp_path):
    a, b, c = (write(tmp_path, n, t) for n, t in (("a", "x\n"), ("b", "x\n"), ("c", "y\n")))
    assert gate.identical_bytes(a, b)[0] is True
    same, sha = gate.identical_bytes(a, c)
    assert same is False and len(sha) == 12



def test_log_problems_flags_glued_and_duplicate_fields(tmp_path):
    good = "## [2026-01-01T00:00:00Z] a\n\nContext:\ntool=Claude Code\nmodel=claude-sonnet-5-5\n\n"
    log = tmp_path / "log.txt"
    log.write_text(good, encoding="utf-8")
    assert gate.log_problems(log) == []
    log.write_text(good.rstrip("\n") + "## [2026-01-01T00:00:01Z] b\ntool=X\nmodel=Y\n", encoding="utf-8")
    assert any("glued" in p for p in gate.log_problems(log))
    log.write_text(good + "## [2026-01-01T00:00:02Z] c\ntool=X\ntool=X\nmodel=unknown\n", encoding="utf-8")
    assert any("bad tool/model" in p for p in gate.log_problems(log))
    assert gate.log_problems(ROOT / "log.txt") == []   # the real transcript
