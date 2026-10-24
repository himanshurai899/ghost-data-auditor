---
name: memory-keeper
description: Reads and updates the shared agent memory in .agents/memory/ (progress board, decisions, verified dataset facts, pitfalls). Use at session start to load context, after any gate run or merged change to update progress, when a design decision is made, and when a dataset fact is verified or a pitfall is discovered.
---

# Memory Keeper

Agent memory is plain Markdown in git, so every tool and session sees the same state.

## Files

| File | Holds | Update when |
|---|---|---|
| `MEMORY.md` | index: one line per file + current phase + top 3 next issues | phase changes or next issues change |
| `progress.md` | backlog status table (id, status, owner, evidence of done) | an issue starts, passes its gate, or is blocked |
| `decisions.md` | numbered ADR-lite entries (context → decision → consequence) | any choice that future agents must not re-litigate |
| `dataset_facts.md` | **verified** facts about the data, each with how it was verified | a fact is verified (with command or sample case id) |
| `pitfalls.md` | traps hit and the fix | a bug costs more than 10 minutes, or a gate fails unexpectedly |

## Rules

- **Facts must be verified.** Every entry in `dataset_facts.md` carries a `Verified by:` line (a command, or sample case ids). Unverified ideas go into `architecture.md` §4.4 hypotheses.
- **Never store** secrets, raw request text, or unmasked identifiers. Use resource ids and case ids instead of emails.
- **Edit in place** rather than appending duplicates. Delete entries that turn out to be wrong, and note the correction in `decisions.md`.
- **Keep it short.** Each file is read at session start, so link to docs instead of copying them.

## Session-start read order

`MEMORY.md` → `progress.md` → (task-specific) `decisions.md` / `dataset_facts.md` / `pitfalls.md`.
