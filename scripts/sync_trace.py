"""Mirror this project's Claude Code session traces into agent-trace/claude-code/, secrets redacted (T18).

Run by the Stop hook after every turn (.claude/settings.local.json), or by hand:
    python scripts/sync_trace.py
Copies session JSONL, subagent transcripts and persisted tool outputs from
~/.claude/projects/<encoded repo path>* (worktree folders included), skipping the `memory/` store.
Incremental: a file is rewritten only when its source changed. agent-trace/ is gitignored.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate import SECRET_PATTERNS  # noqa: E402  same patterns the security gate scans for

SKIP_DIRS = {"memory"}


def encode(path: Path) -> str:
    """Claude Code's project folder name: every non-alphanumeric character becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def redact(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: "nvapi-[REDACTED]" if m.group().startswith("nvapi-") else "[REDACTED]", text)
    return text


def project_dirs(repo: Path, projects_root: Path) -> list[Path]:
    enc = encode(repo).lower()
    if not projects_root.is_dir():
        return []
    return sorted(d for d in projects_root.iterdir()
                  if d.is_dir() and (d.name.lower() == enc or d.name.lower().startswith(enc + "-")))


def sync(repo: Path, projects_root: Path, dest: Path) -> int:
    copied = 0
    for proj in project_dirs(repo, projects_root):
        for src in proj.rglob("*"):
            rel = src.relative_to(proj)
            if not src.is_file() or SKIP_DIRS & set(rel.parts):
                continue
            out = dest / proj.name / rel
            st = src.stat()
            if out.exists() and out.stat().st_mtime_ns == st.st_mtime_ns:
                continue
            try:
                text = src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # can't verify redaction of a binary file, so it is not copied
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(redact(text), encoding="utf-8", newline="")
            os.utime(out, ns=(st.st_atime_ns, st.st_mtime_ns))
            copied += 1
    for loose in (dest.glob("*") if dest.is_dir() else ()):  # e.g. a /export transcript saved here by hand
        if loose.is_file():
            try:
                text = loose.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if redact(text) != text:
                loose.write_text(redact(text), encoding="utf-8", newline="")
    return copied


if __name__ == "__main__":
    try:
        sync(ROOT, Path.home() / ".claude" / "projects", ROOT / "agent-trace" / "claude-code")
    except Exception as e:  # never break the session over a trace copy
        print(f"sync_trace: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(0)
