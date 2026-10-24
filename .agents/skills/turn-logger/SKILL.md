---
name: turn-logger
description: Appends the AGENTS.md-mandated SESSION START and per-turn entries to the root log.txt with correct tool= and model= values, redacting secrets and personal data. Use at the start of every session and at the end of every user turn, including sub-agent turns.
---

# Turn Logger

`log.txt` is a graded deliverable (the chat transcript). If an entry is missing or malformed, points are lost.

## Rules (AGENTS.md §2, §5)

- Path: `log.txt` next to the top-level `AGENTS.md`. Resolve it relative to that file. Never write a private copy.
- **Append only.** Never rewrite, reorder or delete earlier entries.
- UTF-8 with `\n` line endings.
- `tool=` is the exact harness name (for example `Claude Code`, `Codex CLI`, `Gemini CLI`, `Cursor`). `model=` is the exact runtime model id from session metadata. Never write `unknown`, a model family name, or a guess.
- Redact keys, tokens, cookies and credentials as `[REDACTED]`. Don't paste dataset identifiers (emails, phones) or large file contents. Refer to files by path instead.
- Sub-agents set `parent_agent=<parent name>` and write to the same file.

## Per-turn entry

```text
## [<ISO-8601 UTC>] <short title, max 80 chars>

User Prompt (verbatim, secrets redacted):
<exact user message>

Agent Response Summary:
<2-5 sentences: what was done, why, key decisions>

Actions:
* <file edited / command run / tool invoked>

Context:
tool=<harness>
model=<exact model id>
branch=<git branch>
repo_root=<absolute path>
worktree=<path or main>
parent_agent=<name or none>
```

## Procedure

1. Write the entry with a single append. In a POSIX shell, use a heredoc to `>> log.txt`. In Python, use `open(path, "a", encoding="utf-8", newline="\n")`.
2. Re-read the tail of the file. Confirm it has exactly one populated `tool=` line and exactly one populated `model=` line.
3. If the user prompt contains pasted secrets, replace them with `[REDACTED]` before writing.
