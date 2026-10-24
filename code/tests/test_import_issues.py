import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("import_issues", ROOT / "scripts" / "import_issues.py")
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)


def test_plan_builds_arg_lists_for_labels_milestones_issues():
    rows = imp.load(ROOT / "docs" / "github_issues.csv")
    cmds = imp.plan("me/repo", rows, existing_titles={rows[0]["title"]})
    assert all(isinstance(c, list) and c[0] == "gh" for c in cmds)  # never a shell string
    issue_cmds = [c for c in cmds if c[1:3] == ["issue", "create"]]
    assert len(issue_cmds) == len(rows) - 1                           # idempotent: existing title skipped
    first = issue_cmds[0]
    assert first[first.index("--milestone") + 1].startswith("P")
    labels = {c[c.index("label") + 2] for c in cmds if "label" in c}
    assert {"phase:p1", "security", "priority:high"} <= labels
