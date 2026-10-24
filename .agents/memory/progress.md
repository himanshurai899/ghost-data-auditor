# Progress board

Repo: https://github.com/himanshurai899/ghost-data-auditor (private). Backlog id `P<phase>-<nn>` ↔ GitHub issue `#N` (#1–#51 follow CSV order).
Status: `todo` · `doing` · `blocked` · `done` (done = issue closed with an evidence comment).
Convention: commit `P1-05 (#14): <what> (tests: test_evidence.py)`. Put `Closes #14` in the commit body or PR when the acceptance criteria are met.

## Done

| Id | # | Evidence |
|---|---|---|
| P0-01 … P0-09 | #1–#9 | caf882b; closing comments on each issue |
| P1-03 Scorer | #12 | caf882b; test_scorer.py (5); baseline row in audit/gate_log.md |
| P1-04 Safety | #13 | caf882b; test_safety.py (18), red → green |
| P1-13 Run trail + report | #22 | caf882b; test_audit.py (4), red → green |

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

Later phases: P2 #24–#32 · P3 #33–#40 · P4 #41–#46 · P5 #47–#51.

## Metrics trail

| When | Commit | Tests | Sample status | Step F1 | Sequence | Note |
|---|---|---|---|---|---|---|
| 2026-10-24 | caf882b | 57 pass | 0.000 | 0.000 | 0.000 | skeleton baseline (stages stubbed) |
