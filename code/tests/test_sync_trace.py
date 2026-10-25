import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("sync_trace", ROOT / "scripts" / "sync_trace.py")
st = importlib.util.module_from_spec(spec)
spec.loader.exec_module(st)

FAKE_KEY = "nvapi-" + "k" * 40  # built at runtime: no key-shaped literal in the repo


def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def setup(tmp_path):
    repo = Path("C:/Work/my-repo")
    projects = tmp_path / "projects"
    mine = projects / st.encode(repo)
    write(mine / "s1.jsonl", '{"msg": "key is ' + FAKE_KEY + '"}\n')
    write(mine / "s1" / "subagents" / "agent-1.jsonl", '{"msg": "hello"}\n')
    write(mine / "s1" / "tool-results" / "r.txt", "NVIDIA_API_KEY=" + FAKE_KEY + "\n")
    write(mine / "memory" / "MEMORY.md", "private memory\n")
    write(projects / (st.encode(repo) + "--claude-worktrees-agent-x") / "w.jsonl", "{}\n")
    write(projects / "c--Other-project" / "o.jsonl", "{}\n")
    return repo, projects, tmp_path / "agent-trace" / "claude-code"


def test_encode_matches_claude_folder_naming():
    assert st.encode(Path("c:/Himanshu/Projects/hackerrank-orchestrate-october26")) == \
        "c--Himanshu-Projects-hackerrank-orchestrate-october26"


def test_sync_copies_this_project_redacted_and_skips_memory_and_other_projects(tmp_path):
    repo, projects, dest = setup(tmp_path)
    copied = st.sync(repo, projects, dest)
    files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    base = st.encode(repo)
    assert files == sorted([f"{base}/s1.jsonl", f"{base}/s1/subagents/agent-1.jsonl", f"{base}/s1/tool-results/r.txt",
                            f"{base}--claude-worktrees-agent-x/w.jsonl"])
    assert copied == 4
    blob = "".join(p.read_text(encoding="utf-8") for p in dest.rglob("*") if p.is_file())
    assert FAKE_KEY not in blob and "nvapi-[REDACTED]" in blob


def test_sync_is_incremental(tmp_path):
    repo, projects, dest = setup(tmp_path)
    st.sync(repo, projects, dest)
    assert st.sync(repo, projects, dest) == 0
    write(projects / st.encode(repo) / "s1.jsonl", '{"msg": "more"}\n')
    assert st.sync(repo, projects, dest) == 1


def test_missing_projects_root_is_a_noop(tmp_path):
    assert st.sync(Path("C:/x"), tmp_path / "nope", tmp_path / "dest") == 0


def test_loose_files_in_dest_like_slash_export_are_redacted_in_place(tmp_path):
    repo, projects, dest = setup(tmp_path)
    export = write(dest / "2026-10-25-export.txt", "user pasted " + FAKE_KEY + "\n")
    st.sync(repo, projects, dest)
    assert FAKE_KEY not in export.read_text(encoding="utf-8")
