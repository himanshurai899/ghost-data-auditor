# Progress board

Repo: https://github.com/himanshurai899/ghost-data-auditor (private). Backlog id `P<phase>-<nn>` ↔ GitHub issue `#N` (#1–#51 follow CSV order).
Status: `todo` · `doing` · `blocked` · `done` (done = issue closed with an evidence comment).
Gitflow (D-014): `feature/<#>-<slug>` from `develop` → PR → `develop`; phase exit `release/p<n>` → `main` + tag. Commit `P1-05 (#14): <what>`.
PRs into `develop` don't auto-close issues (GitHub only auto-closes on the default branch), so close them manually with an evidence comment after the merge. Max 5 parallel agents (D-019), each in its own worktree.

## Done

| Id | # | Evidence |
|---|---|---|
| P0-01 … P0-09 | #1–#9 | caf882b; closing comments on each issue |
| P1-03 Scorer | #12 | caf882b; test_scorer.py (5); baseline row in audit/gate_log.md |
| P1-04 Safety | #13 | caf882b; test_safety.py (18), red → green |
| P1-13 Run trail + report | #22 | caf882b; test_audit.py (4), red → green |
| P1-02 Contract module | #11 | PR #54; typed loaders dropped (D-015); planner-stub safety net |
| P1-07 Identity | #16 | PR #55; 518/518 resolve (case-insensitive); test_identity.py 12 |
| P1-08 Intent rules | #17 | PR #56; 508 DELETE / 10 NOT_DELETE / 0 UNKNOWN; test_intent.py 57 |
| P1-01 Dataset forensics | #10 | PR #58; docs/evidence_field_map.md, F-011..F-022, D-016 |
| P2-10 NVIDIA retrieval client | #52 | PR into develop; test_llm.py (19, red → green) + live smoke (3, RUN_LIVE=1) |

| P1-05 umbrella + parsers | #14 #60 #61 #62 | PR #59 #67 #68 #69; 4,465 facts from 94 files, 0 quarantined |
| P1-06 Activity claims | #15 | PR #66 |
| P1-09 Temporal linker | #18 | PR #65; --strict-temporal (D-017) |
| P1-10/11 State + policy | #19 #20 | PR #70 |
| P1-12 Planner | #21 | PR #71 |

## Open, P1 MVP (next up, in order)

| Id | # | Status | Owner | Note |
|---|---|---|---|---|
| P1-06 Activity/audit facts | #15 | todo | implementer | |
| P1-09 Temporal linker | #18 | todo | implementer | D-017 switch `--strict-temporal`; report both readings |
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
| 2026-10-25 | 82a4922 | 147 pass + 3 live | 0.000 | 0.000 | 0.000 | identity + intent merged; planner still a stub |
| 2026-10-25 | P1 end | 209 pass + 3 live | 0.969 | 0.943 | 0.531 | P1 phase gate: suite + gates PASS; full run 518 rows, 151/357/10 |
