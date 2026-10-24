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

**D-010 — NVIDIA keys: one account-scoped default + optional per-endpoint overrides** · 2026-10-25 · accepted
The user generated 4 keys on separate model pages. A probe showed the embed-1b key also authorizes chat, so keys are account-scoped. → `NVIDIA_API_KEY` is the default; `NVIDIA_API_KEY_{EMBED,EMBED_LARGE,RERANK,PARSE,CHAT}` override it. The user's `.env` variable names were renamed to these, with all values preserved. → Chat models need no extra key.

**D-011 — Stdlib HTTP for all NVIDIA calls; `openai` dependency dropped** · 2026-10-25 · accepted
Parse needs multipart and rerank uses a non-OpenAI path, so the SDK covered only part of the surface. → `ghost/llm.py` uses `urllib` with an injectable transport, which makes it fully unit-testable. → One fewer supply-chain dependency (T10).

**D-012 — Nemotron Parse is the primary screenshot/page extractor** · 2026-10-25 · accepted
Live test on an evidence PNG returned the archive table (resource ids, accounts, regions, dates) as LaTeX tabular plus layout tags. → P2-02 parses that Markdown deterministically; the VL chat model is only a fallback for visual-only states. → Fewer free-form LLM calls; the output can be parsed by tests.

**D-013 — Retrieval models: embed-1b for intent kNN; embed-8b + rerank-8b for console RAG** · 2026-10-25 · accepted
The user chose embed-1b, embed-8b, rerank-8b and parse. embed-8b timed out server-side during probing. → Never mix vector spaces inside one index; fall back to 1b for a whole index, not per item.

**D-014 — Gitflow + coordinator-driven parallelism (max 3 agents, worktrees)** · 2026-10-25 · accepted
User instruction. → feature/bugfix branches from `develop` come back through PRs once gates pass; phase releases go `release/p<n>` → `main` with a tag; hotfixes branch from `main`. The coordinator runs at most 3 agents, each in its own worktree, on dependency-free issues with disjoint files. Merges into `main` need user confirmation.

**D-015 — No typed loader classes; `contract.read_csv` dicts are the data model for CSV inputs** · 2026-10-25 · accepted
The remaining P1-02 (#11) item was dataclasses per CSV. Every consumer reads a handful of columns, and the validator already enforces the output schema. → Typed loaders dropped (YAGNI). Each stage reads its own CSVs via `read_csv(path, header)`, which rejects unexpected headers. → #11 closed; #16 and #17 unblocked. Pipeline gets a temporary safety net: a planner `NotImplementedError` degrades to a NOT_APPLICABLE placeholder with a WARN trail event (removed in #21).
