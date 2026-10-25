# Pitfalls

Format: **symptom** → cause → fix.

- **Python's `sorted()` on case ids puts `case_100` before `case_33`** → lexicographic sort → use numeric sort (F-002). `contract.case_sort_key` does this.
- **Windows console prints `·`/`—` as `�`** → cp1252 console, not file corruption → files are UTF-8; set `PYTHONIOENCODING=utf-8` when piping.
- **A shallow clone can't be pushed to a new remote** → "shallow update not allowed" → `git fetch --unshallow upstream` before the first push.
- **Git warns "LF will be replaced by CRLF"** → global `core.autocrlf=true` on Windows; AGENTS.md wants `\n` in log.txt → `.gitattributes` with `* text=auto eol=lf`.
- **The security gate flags `sample_output` in any pipeline file, even inside a docstring** → this is intended (T8) → name prediction files `runs/sample_pred.csv`; don't allowlist.
- **embed-8b returns 504 "service request timed out after 120s"** → free-tier cold start or overload → the client retries with a 150 s timeout. If 8b stays down, rebuild the whole index on embed-1b. Never mix vectors from the two models.
- **Nemotron chat models answered with `content: null` and only `reasoning_content`** → reasoning mode used up `max_tokens` → disable thinking (`chat_template_kwargs: {"enable_thinking": false}` or a `/no_think` system prompt, per model card) and set realistic `max_tokens` (P2-01).
- **The IDE auto-attached `.env` (with keys) to the agent chat** → the keys are now inside the Claude Code session JSONL → redact `nvapi-…` in every trace file before building `agent-trace.zip`, and rotate the keys after the event (T18).
- **Parse request bodies use a random multipart boundary, which breaks caching** → derive the boundary from the image's sha256 (done in `llm.parse_page`).
- **Agent worktrees start from `main`, not `develop`** → the agent works on stale code (missing guards, conflicting memory files) → brief says `git switch -c feature/... origin/develop`; the coordinator rebases before merging.
- **`git worktree remove` gets "Permission denied" on Windows** → a process still holds a file lock → delete the folder, then `git worktree prune`.
- **`.claude/worktrees/` was not gitignored** → `git add -A` could commit agent worktrees as embedded repos → now ignored and enforced by `gate.py security` (`unignored()`).
