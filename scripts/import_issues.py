"""Create GitHub labels, milestones and issues from docs/github_issues.csv via the gh CLI.

    python scripts/import_issues.py --repo OWNER/NAME            # dry run: print what would happen
    python scripts/import_issues.py --repo OWNER/NAME --apply    # do it (idempotent: skips existing titles)
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"phase": "5319e7", "priority": "d93f0b", "security": "b60205", "wow": "fbca04", "future": "c5def5"}


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def plan(repo: str, rows: list[dict], existing_titles=frozenset(), existing_milestones=frozenset()) -> list[list[str]]:
    labels = sorted({lab for r in rows for lab in r["labels"].split(",")})
    cmds = [["gh", "label", "create", lab, "--repo", repo, "--force", "--color",
             COLORS.get(lab.split(":")[0], "0e8a16")] for lab in labels]
    for m in sorted({r["milestone"] for r in rows} - set(existing_milestones)):
        cmds.append(["gh", "api", f"repos/{repo}/milestones", "-f", f"title={m}"])
    for r in rows:
        if r["title"] not in existing_titles:
            cmds.append(["gh", "issue", "create", "--repo", repo, "--title", r["title"], "--body", r["body"],
                         "--label", r["labels"], "--milestone", r["milestone"]])
    return cmds


def _gh_lines(args: list[str]) -> set[str]:
    return set(subprocess.run(args, capture_output=True, text=True, check=True).stdout.splitlines())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--csv", type=Path, default=ROOT / "docs" / "github_issues.csv")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    rows = load(a.csv)
    titles = milestones = set()
    if a.apply:
        titles = {i["title"] for i in json.loads(subprocess.run(
            ["gh", "issue", "list", "--repo", a.repo, "--state", "all", "--limit", "1000", "--json", "title"],
            capture_output=True, text=True, check=True).stdout)}
        milestones = _gh_lines(["gh", "api", f"repos/{a.repo}/milestones?state=all", "--paginate", "--jq", ".[].title"])
    cmds = plan(a.repo, rows, titles, milestones)
    for c in cmds:
        shown = [x if len(x) < 60 else x[:57] + "..." for x in c]
        print(" ".join(shown))
        if a.apply:
            subprocess.run(c, check=True, capture_output=True)
    print(f"{'applied' if a.apply else 'dry run'}: {len(cmds)} commands")
    return 0


if __name__ == "__main__":
    sys.exit(main())
