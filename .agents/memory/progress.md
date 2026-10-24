# Progress board

Repo: https://github.com/himanshurai899/ghost-data-auditor (private). Backlog id `P<phase>-<nn>` ↔ GitHub issue `#N` (#1–#51 follow CSV order).
Status: `todo` · `doing` · `blocked` · `done` (done = issue closed with an evidence comment).
Gitflow (D-014): `feature/<#>-<slug>` from `develop` → PR → `develop`; phase exit `release/p<n>` → `main` + tag. Commit `P1-05 (#14): <what>`.
PRs into `develop` don't auto-close issues (GitHub only auto-closes on the default branch), so close them manually with an evidence comment after the merge. Max 3 parallel agents, each in its own worktree.

## Done

| Id | # | Evidence |
|---|---|---|
| P0-01 … P0-09 | #1–#9 | caf882b; closing comments on each issue |
| P1-03 Scorer | #12 | caf882b; test_scorer.py (5); baseline row in audit/gate_log.md |
| P1-04 Safety | #13 | caf882b; test_safety.py (18), red → green |
| P1-13 Run trail + report | #22 | caf882b; test_audit.py (4), red → green |
| P2-10 NVIDIA retrieval client | #52 | PR into develop; test_llm.py (19, red → green) + live smoke (3, RUN_LIVE=1) |

## Open, P1 MVP (next up, in order)

| Id | # | Status | Owner | Note |
|---|---|---|---|---|
| P1-01 Dataset forensics + H1–H6 | #10 | todo | data-analyst | critical path start |
| P1-02 Contract module | #11 | doing | implementer | validator done; typed loaders remain |
| P1-05 Evidence ingest | #14 | todo | implementer | after P1-01 |
| P1-06 Activity/audit facts | #15 | todo | implementer | |
| P1-07 Identity | #16 | todo | implementer | parallel with P1-05 (disjoint files) |
| P1-08 Intent rules | #17 | todo | implementer | parallel with P1-05 |
| P1-09 Temporal linker | #18 | todo | implementer | |
| P1-10 State reconstruction | #19 | todo | implementer | |
| P1-11 Policy engine | #20 | todo | implementer | |
| P1-12 Planner | #21 | todo | implementer | |
| P1-14 Full run v1 + report v1 | #23 | todo | evaluator | MVP exit |

P2-01 #24 is partly covered by #52 (cache, retry, throttle, meter, offline); chat `complete()` remains.
Later phases: P2 #24–#32 · P3 #33–#40 · P4 #41–#46 · P5 #47–#51.

## Metrics trail

| When | Commit | Tests | Sample status | Step F1 | Sequence | Note |
|---|---|---|---|---|---|---|
| 2026-10-24 | caf882b | 57 pass | 0.000 | 0.000 | 0.000 | skeleton baseline (stages stubbed) |
| 2026-10-25 | feature/52 | 76 pass + 3 live | 0.000 | 0.000 | 0.000 | NVIDIA client; no pipeline logic yet |
