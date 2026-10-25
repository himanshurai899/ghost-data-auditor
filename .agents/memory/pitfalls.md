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
- **eval gate reported "regressed: status 0.969 -> 0.969"** → the baseline is parsed from gate_log.md at 3 decimals, the current value is exact (0.96875) → compare at the logged precision (`gate.regressions`, fixed 2026-10-25, covered by test_regressions).
- **`/api/ask` returned 422 for the contract's own body** → `ask.py` has `from __future__ import annotations` and defined the pydantic model inside `register()`, so FastAPI could not resolve `req: Ask` and treated it as a query parameter → request model at module level (`AskRequest`). Live-verified.
- **Merge script closed issues and deleted worktrees after a failed merge** ("Base branch was modified" race right after another merge) → always poll `gh pr view --json state` until MERGED before closing/cleaning; wait for `mergeable` to leave UNKNOWN.
- **NVIDIA topic-control (nemoguard) returned HTTP 500** → server-side CUDA error → `ask.check_guard` does deterministic keyword refusal first and trips a circuit breaker after the first hard failure (D-022).
- **log.txt entry glued to the next header** → an agent appended without a trailing newline → `gate.log_problems` (security gate) now fails on glued headers and on entries without exactly one tool=/model= line.
- **Emails in logs/JSON made quadratic regex scans** → see security review below.

## Security review of 2026-10-25 (PR #88, 9 findings, all fixed with regression tests)

| # | Severity | Finding |
|---|---|---|
| 1 | High | email regexes in safety/ev_sql/ev_page were quadratic on long runs without "@" (mask_text runs on every trail event → a long token could hang a run) |
| 2 | High | secret pattern missed JSON-escaped values in session transcripts (`\"api_key\": \"...\"`) so sync_trace and the gate could miss them |
| 3 | Medium | sandboxed SQLite progress handler was removed after load: later queries ran unmetered |
| 4 | Medium | zero-width / soft-hyphen / fullwidth characters split the injection marker; `normalize` now strips Cf and uses NFKD |
| 5 | Medium | `llm._redact` only knew the `nvapi-` pattern; now also strips exact env key values and timeout text |
| 6 | Medium | NUL byte / over-long manifest path raised out of `safe_evidence_path` and crashed ingest; now quarantined |
| 7 | Medium | `file_id` used unchecked in the ev_page cache path; must match `[A-Za-z0-9_-]+` |
| 8 | Low | PDF page count uncapped despite the threat model; now 50 pages |
| 9 | Low | ev_sql interpolated a table name before validating it; unknown tables rejected first |
