---
name: submission-packager
description: Produces the final HackerRank submission — cold full run, regenerated evaluation and usage reports, allowlisted code.zip, log.txt check, and the pre-submission checklist. Use only in phase P4 or when the user asks to package or submit.
---

# Submission Packager

## Steps

1. `python code/main.py` (cold cache if time allows) writes `output.csv` at the repo root. G7 must PASS.
2. `python code/evaluation/main.py --write-report` and `python code/evaluation/usage.py --run <run_id>` regenerate the reports.
3. `python scripts/gate.py all` must show contract, eval, security and package all PASS.
4. Review the `code.zip` listing. It must contain `code/**`, `README.md` and `evaluation/*.md`. It must contain **no** `dataset/`, `.env`, `runs/`, `.cache/`, `node_modules/`, venvs or nested zips.
5. Re-read the AGENTS.md "Pre-submission checklist" in the root README.
6. **Agent trace.** A Stop hook (`.claude/settings.local.json` → `scripts/sync_trace.py`) mirrors this project's Claude Code session files, subagent transcripts and tool outputs into the gitignored `agent-trace/claude-code/` after every turn, with secrets redacted (T18). The user also runs `/export` and saves the readable transcript into `agent-trace/claude-code/`. Then run `python scripts/sync_trace.py` once more, which also redacts files saved there by hand. Verify with `grep -rE "nvapi-[A-Za-z0-9_-]{20,}" agent-trace` (must print nothing). Then zip: `Compress-Archive -Path .gent-trace -DestinationPath .gent-trace.zip -Force`. Agents never copy auth files. Recommend rotating the keys after submission.
7. Submission URL (always give it in full): https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

## Never

- Submit or upload on the user's behalf.
- Include the `web/` console in `code.zip` unless the user asks. It isn't needed to reproduce `output.csv`. Ask the user.
