# Progress board

Status: `todo` · `doing` · `blocked` · `done` (done needs evidence: a gate_log row, command output, or commit).

| Id | Title | Status | Owner | Evidence of done |
|---|---|---|---|---|
| P0-01 | Private repo + upstream | done | coordinator | see decisions D-005 |
| P0-02 | Agent layer `.agents/` | done | coordinator | files in `.agents/agents`, `.claude/` pointers |
| P0-03 | Prompt-enhancer skill + agent | done | coordinator | `.agents/skills/prompt-enhancer/` |
| P0-04 | Memory seeded | done | coordinator | this folder |
| P0-05 | Executable gates + gate log | done | coordinator | `audit/gate_log.md` first rows |
| P0-06 | Pipeline walking skeleton | done | coordinator | `python code/main.py` → 518 rows, contract PASS |
| P0-07 | Secure config baseline | done | coordinator | `.gitignore`, `.env.example`, pinned requirements |
| P0-08 | Backlog CSV + importer | done | coordinator | `docs/github_issues.csv`, `scripts/import_issues.py` (dry run) |
| P0-09 | React console scaffold | done | coordinator | `web/` builds |
| P1-01 | Dataset forensics + H1–H6 | todo | data-analyst | |
| P1-02 | Contract module | todo | implementer | validator exists from P0; needs loaders + unit checks |
| P1-03 | Scorer | todo | evaluator | scorer exists from P0; needs baseline row |
