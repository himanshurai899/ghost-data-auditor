"""Executable dev gates (architecture.md §5). Every run appends a row to audit/gate_log.md.

    python scripts/gate.py contract   # G7 on ./output.csv
    python scripts/gate.py eval       # sample run + scorer + no-regression vs last PASS
    python scripts/gate.py determinism # two offline sample runs must be byte-identical
    python scripts/gate.py security   # secrets, unsafe APIs, golden leak, PII, .env tracking (DG5)
    python scripts/gate.py package    # build code.zip from an allowlist and scan it
    python scripts/gate.py all
Set AGENT_NAME to record who ran the gate. Exit code 1 if any gate FAILs.
"""
import csv
import os
import re
import hashlib
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "audit" / "gate_log.md"
sys.path.insert(0, str(ROOT / "code"))

SECRET_PATTERNS = [re.compile(p) for p in (
    r"nvapi-[A-Za-z0-9_\-]{20,}",
    r"\bsk-[A-Za-z0-9_\-]{20,}",
    r"\bgh[pousr]_[A-Za-z0-9]{30,}",
    r"github_pat_[A-Za-z0-9_]{30,}",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    # also matches the JSON-escaped form found in session transcripts: \"api_key\": \"value\" (T18)
    r"(?i)(api[_-]?key|secret|token|password)\\?['\"]?\s*[:=]\s*\\?['\"][^'\"\s\\]{16,}",
)]
UNSAFE_PATTERNS = [re.compile(p) for p in (
    r"\beval\(", r"\bexec\(", r"\bpickle\.loads?\(", r"shell\s*=\s*True", r"\bos\.system\(",
)]
UNSAFE_UI = re.compile(r"dangerouslySetInnerHTML")
SKIP_PARTS = {"__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "dist", ".git"}


def rel(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


def repo_files(root: Path = ROOT) -> list[Path]:
    """Tracked + untracked-but-not-ignored files, excluding the organizer dataset."""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    return [root / f for f in out if not f.startswith("dataset/") and (root / f).is_file()]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def scan_secrets(files, root) -> list[str]:
    return [f"{rel(p, root)}: {pat.pattern[:24]}" for p in files for pat in SECRET_PATTERNS if pat.search(_read(p))]


def scan_unsafe(files, root) -> list[str]:
    hits = []
    for p in files:
        r, text = rel(p, root), _read(p)
        if p.suffix == ".py" and r.split("/")[0] in ("code", "scripts"):
            hits += [f"{r}: {pat.pattern}" for pat in UNSAFE_PATTERNS if pat.search(text)]
        if p.suffix in (".ts", ".tsx", ".js", ".jsx") and r.startswith("web/src/") and UNSAFE_UI.search(text):
            hits.append(f"{r}: dangerouslySetInnerHTML")
    return hits


def scan_golden_leak(files, root) -> list[str]:
    """Only code/evaluation (and tests) may reference the gold sample answers (T8)."""
    return [rel(p, root) for p in files
            if rel(p, root).startswith("code/") and not rel(p, root).startswith(("code/evaluation/", "code/tests/"))
            and p.suffix == ".py" and "sample_output" in _read(p)]


def dataset_emails() -> set[str]:
    d = ROOT / "dataset"
    with open(d / "user_identities.csv", encoding="utf-8") as f:
        emails = {r["email"] for r in csv.DictReader(f)}
    with open(d / "user_audit_log.csv", encoding="utf-8") as f:
        emails |= {v for r in csv.DictReader(f) if r["field_name"] == "email" for v in (r["old_value"], r["new_value"])}
    return {e for e in emails if e}


def scan_pii(files, root, emails: set[str]) -> list[str]:
    hits = []
    for p in files:
        text = _read(p)
        hits += [f"{rel(p, root)}: {e}" for e in sorted(emails) if e in text]
    return hits


REQUIRED_IGNORED = (".env", ".env.local", "runs/", ".cache/", ".venv/", "code.zip", ".claude/worktrees/", "2026-01-01-000000-pastedcontent-x.txt", ".ghost/",
                    ".claude/settings.local.json", "web/node_modules/", "web/dist/", "agent-trace/", ".ghost/")


def unignored(root: Path = ROOT) -> list[str]:
    """Local-only paths (secrets, runtime output, agent worktrees) that .gitignore fails to exclude (T1, T9)."""
    return [p for p in REQUIRED_IGNORED
            if subprocess.run(["git", "check-ignore", "-q", "--no-index", p], cwd=root).returncode != 0]


def log_problems(log: Path) -> list[str]:
    """AGENTS.md section 5 format: every entry has exactly one populated tool= and model= line, no glued headers."""
    if not log.exists():
        return ["log.txt missing"]
    text = log.read_text(encoding="utf-8")
    problems = [f"header glued to previous line at offset {m.start()}" for m in re.finditer(r"(?<=\S)## \[20", text)]
    for b in (b for b in re.split(r"(?m)^(?=## \[)", text) if b.startswith("## [")):
        tools, models = re.findall(r"(?m)^tool=(.*)$", b), re.findall(r"(?m)^model=(.*)$", b)
        if len(tools) != 1 or len(models) != 1 or not tools[0].strip() or not models[0].strip()                 or models[0].strip().lower() in ("unknown", "ai") or "<" in tools[0] + models[0]:
            problems.append(f"bad tool/model fields in entry: {b.splitlines()[0][:60]}")
    return problems


def package_members(root: Path = ROOT) -> list[str]:
    """Allowlist: everything under code/ except caches, secrets, archives (T1, P4-03)."""
    base = root / "code"
    out = []
    for p in base.rglob("*"):
        if not p.is_file() or SKIP_PARTS & set(p.relative_to(base).parts):
            continue
        if p.name.startswith(".env") or p.suffix in (".zip", ".pyc"):
            continue
        out.append(rel(p, base))
    return sorted(out)


# ------------------------------------------------------------------ gate log

HEADER = ("# Dev gate log\n\nAppend-only. Written by `scripts/gate.py`.\n\n"
          "| Time (UTC) | Gate | Verdict | Summary | Actor | Commit |\n|---|---|---|---|---|---|\n")


def _git_sha() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or "none"


def append_log(log: Path, gate: str, verdict: str, summary: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(HEADER, encoding="utf-8", newline="\n")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = f"| {ts} | {gate} | {verdict} | {summary.replace('|', '/')} | {os.environ.get('AGENT_NAME', 'cli')} | {_git_sha()} |\n"
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write(row)


def last_eval_baseline(log: Path) -> dict | None:
    if not log.exists():
        return None
    best = None
    for line in log.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[1] == "eval" and cells[2] == "PASS":
            best = {k: float(v) for k, v in re.findall(r"(\w+)=([0-9.]+)", cells[3])}
    return best


def regressions(prev: dict | None, cur: dict) -> list[str]:
    if not prev:
        return []
    # the log stores 3 decimals, so compare at that precision (0.96875 must not 'regress' from a logged 0.969)
    return [f"{k} {prev[k]:.3f} -> {cur[k]:.3f}" for k in prev if k in cur and round(cur[k], 3) < round(prev[k], 3)]


# ------------------------------------------------------------------ gates

def gate_contract():
    from ghost.contract import DATASET, validate_output
    out = ROOT / "output.csv"
    if not out.exists():
        return "FAIL", "output.csv missing at repo root"
    errs = validate_output(out, DATASET / "deletion_requests.csv")
    return ("FAIL", f"{len(errs)} errors; first: {errs[0]}") if errs else ("PASS", "output.csv valid (G7)")


def gate_eval():
    from evaluation.main import load, score
    from ghost.contract import DATASET
    from ghost.pipeline import run
    pred = ROOT / "runs" / "gate_eval_sample_output.csv"
    run(DATASET / "sample_deletion_requests.csv", pred)
    m = score(load(pred), load(DATASET / "sample_output.csv"))
    cur = {"status": m["status_accuracy"], "step_f1": m["step_f1"], "field": m["field_accuracy"],
           "seq": m["sequence_accuracy"]}
    summary = " ".join(f"{k}={v:.3f}" for k, v in cur.items()) + f" ({m['cases']} cases)"
    reg = regressions(last_eval_baseline(LOG), cur)
    return ("FAIL", summary + "; regressed: " + ", ".join(reg)) if reg else ("PASS", summary)


def gate_security():
    files = repo_files()
    problems = [f"secret {h}" for h in scan_secrets(files, ROOT)]
    problems += [f"unsafe {h}" for h in scan_unsafe(files, ROOT)]
    problems += [f"golden-leak {h}" for h in scan_golden_leak(files, ROOT)]
    problems += [f"pii {h}" for h in scan_pii(files, ROOT, dataset_emails())]
    tracked_env = subprocess.run(["git", "ls-files", "--", ".env", "code/.env"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
    problems += [f".env tracked: {f}" for f in tracked_env]
    problems += [f"not gitignored: {p}" for p in unignored()]
    problems += [f"log.txt: {x}" for x in log_problems(ROOT / "log.txt")]
    if problems:
        return "FAIL", f"{len(problems)} problems; first: {problems[0]}"
    return "PASS", f"{len(files)} files clean (secrets, unsafe APIs, golden leak, PII, .env)"


def gate_package():
    members = package_members()
    required = {"README.md", "main.py", "evaluation/evaluation_report.md", "evaluation/usage_report.md"}
    missing = sorted(required - set(members))
    zpath = ROOT / "code.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for m in members:
            z.write(ROOT / "code" / m, m)
    leaks = scan_secrets([ROOT / "code" / m for m in members], ROOT / "code")
    if missing or leaks:
        return "FAIL", f"missing={missing} secrets={leaks[:3]}"
    return "PASS", f"code.zip with {len(members)} files, secret scan clean"


def identical_bytes(a: Path, b: Path) -> tuple[bool, str]:
    """(same bytes?, sha256 prefix of the first file)."""
    da, db = Path(a).read_bytes(), Path(b).read_bytes()
    return da == db, hashlib.sha256(da).hexdigest()[:12]


def gate_determinism():
    from ghost.contract import DATASET
    from ghost.pipeline import run
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for n in ("a", "b"):
            run(DATASET / "sample_deletion_requests.csv", d / f"{n}.csv", runs_dir=d / "runs", offline=True)
        same, sha = identical_bytes(d / "a.csv", d / "b.csv")
    return ("PASS", f"2 offline sample runs byte-identical sha256={sha}") if same else ("FAIL", f"outputs differ (first run sha256={sha})")


GATES = {"contract": gate_contract, "eval": gate_eval, "determinism": gate_determinism, "security": gate_security,
         "package": gate_package}


def main(argv) -> int:
    names = list(GATES) if argv[1:] in ([], ["all"]) else argv[1:]
    failed = False
    for name in names:
        if name not in GATES:
            print(f"unknown gate {name}; choose from {', '.join(GATES)} or all")
            return 2
        try:
            verdict, summary = GATES[name]()
        except Exception as e:  # a crashing gate is a failing gate, and it gets logged
            verdict, summary = "FAIL", f"{type(e).__name__}: {e}"
        append_log(LOG, name, verdict, summary)
        print(f"[{verdict}] {name}: {summary}")
        failed |= verdict == "FAIL"
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
