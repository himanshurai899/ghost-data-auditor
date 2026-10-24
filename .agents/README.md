# .agents — tool-agnostic agent team

This folder is the canonical definition of the AI agent team that builds the Ghost Data deletion auditor. It works with any AGENTS.md-aware tool: Claude Code, Codex, Gemini CLI, Cursor, Copilot, opencode and others. Tool-specific folders (such as `.claude/`) only point back here.

## Start here (every session, every tool)

1. Read `../AGENTS.md` in full and log `SESSION START` (skill: `turn-logger`).
2. Load memory: `memory/MEMORY.md` → `memory/progress.md`.
3. Act as the **coordinator** (`agents/coordinator.md`) unless the user names another agent.
4. Run every new ask through the **prompt-enhancer** skill first.

## Team

| Agent | File | Role |
|---|---|---|
| coordinator | `agents/coordinator.md` | routes, gates, records |
| prompt-enhancer | `agents/prompt-enhancer.md` | raw ask → grounded task spec |
| data-analyst | `agents/data-analyst.md` | dataset forensics, verified facts |
| implementer | `agents/implementer.md` | pipeline, API and UI code |
| evaluator | `agents/evaluator.md` | scoring, custom cases, reports |
| security-guardian | `agents/security-guardian.md` | threat model, DG5, hygiene |

## Skills (open Agent Skills format: `skills/<name>/SKILL.md`)

| Skill | Use |
|---|---|
| `prompt-enhancer` | first step on every ask |
| `turn-logger` | `log.txt` entries (mandatory) |
| `memory-keeper` | read and update `memory/` |
| `eval-runner` | score vs samples (DG4) |
| `security-gate` | DG5 checks + manual checklist |
| `submission-packager` | P4 packaging |

## Gated workflow

`ask → DG1 Prompt → DG2 Plan → build → DG3 Build → DG4 Eval → DG5 Security → record → (phase exit) DG6 Release`

Gates run with `python scripts/gate.py <gate>` and append to `audit/gate_log.md`. Full details are in `../docs/architecture.md` §5.

## Adding support for another tool

Add a thin pointer file in that tool's convention that says "follow `.agents/…`". Never copy definitions, because copies drift.
