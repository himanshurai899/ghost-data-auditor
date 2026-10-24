# Decisions (ADR-lite)

Format: **D-nnn — title** · date · status. Then context → decision → consequence.

**D-001 — Deterministic core, LLM at the edges** · 2026-10-24 · accepted
Exact-match scoring and reproducibility. → Identity, temporal, state, policy and ordering are code. The LLM is used for intent (low confidence), vision OCR and flagged adjudication. → The MVP runs with no LLM. LLM issues can't corrupt step lists.

**D-002 — NVIDIA build as LLM provider, via OpenAI-compatible API** · 2026-10-24 · accepted
User choice: free build keys. → `base_url=https://integrate.api.nvidia.com/v1`, key in `NVIDIA_API_KEY`, models per role in env (see `.env.example`). → Rate limit of about 40 rpm is handled with batching, a sha256 cache and a token bucket. Billed cost $0; the usage report shows an estimate at reference rates.

**D-003 — Tech stack: Python pipeline + FastAPI + React (Vite, TS)** · 2026-10-24 · accepted
User choice. The console drives the pipeline (user picked "full app drives pipeline"). → The console calls `pipeline.run()` in-process; the CLI stays the grading path. → API hardening T13–T17 is mandatory.

**D-004 — Tool-agnostic agent layer in `.agents/`** · 2026-10-24 · accepted
User wants it to work with any AI tool. → Canonical agents and skills (open Agent Skills format) live in `.agents/`; AGENTS.md §10 points there; `.claude/` holds thin pointers only. → To add a tool, add pointers, never copies.

**D-005 — Private repo `ghost-data-auditor`; organizer repo as `upstream`** · 2026-10-24 · accepted
User chose "private, custom name" without giving a name. → `himanshurai899/ghost-data-auditor`. Rename with `gh repo rename` if needed. → Pull organizer updates with `git fetch upstream`.

**D-006 — Solo 24 h plan, MVP by H10** · 2026-10-24 · accepted
User: solo, about 24 h. → Phase windows in `docs/delivery_plan.md`, with cut lines defined per phase.

**D-008 — TDD is mandatory** · 2026-10-24 · accepted
User instruction. → Every issue writes failing tests first (red), then code (green), then refactor. DG3 requires evidence of the red run. pytest for Python; vitest arrives with the first UI logic (P3-01). → `contract.py` was spiked before its tests, then covered by tests validated against all 32 gold sample rows. Every module since then went test-first.

**D-009 — Test fixtures use synthetic identifiers** · 2026-10-24 · accepted
`gate.py security` fails on any dataset email in committed files (T9). → Tests use `example.com`/`example.org` values. Real dataset files are read only at test time.

**D-007 — Audit trails: JSONL for machines, Markdown for humans, rendered from the same events** · 2026-10-24 · accepted
User asked for readable audit and logging trails. → `runs/<id>/trail.jsonl` + `report.md` (PII-masked), `audit/gate_log.md` for dev gates. → The two formats can't drift apart.
