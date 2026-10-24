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
6. Remind the user about `agent-trace.zip` (see `agent_trace_instructions.md`). The user creates it; agents never copy auth files.
7. Submission URL (always give it in full): https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

## Never

- Submit or upload on the user's behalf.
- Include the `web/` console in `code.zip` unless the user asks. It isn't needed to reproduce `output.csv`. Ask the user.
