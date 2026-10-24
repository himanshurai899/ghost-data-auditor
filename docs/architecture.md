# Ghost Data Still Exists — System Design

Status: v1 (baseline design) · Owner: coordinator agent · Last updated: 2026-10-24
Related: [delivery_plan.md](delivery_plan.md) · [github_issues.csv](github_issues.csv) · [../AGENTS.md](../AGENTS.md) · [../problem_statement.md](../problem_statement.md)

---

## 1. Problem in one paragraph

For each of 518 deletion requests, decide `COMPLETE | INCOMPLETE | NOT_APPLICABLE` at the case's `audit_at`. Then emit an ordered, evidence-cited `steps_json` made of findings, remediation and verification steps. The inputs are a global, noisy evidence corpus: 94 files (SQL snapshots, JSON, logs, PDFs, PNG screenshots), 4,011 activity events, 306 identity-change audit rows and 850 identities, plus a 15-rule policy table. Workflow statuses and activity results are **claims**. Only observed state counts as truth.

## 2. Architectural stance

| Principle | Decision | Why |
|---|---|---|
| **Deterministic core, LLM at the edges** | Identity, temporal filtering, state reconstruction, policy and ordering are plain code. LLMs only classify intent (multilingual free text), read pixels (PNG/PDF) and adjudicate flagged ambiguity. | Every scoring dimension is exact-match. Code is reproducible, cheap and testable. LLM output can't silently corrupt a step list. |
| **Facts, not files** | Every evidence item is normalized once into a uniform `Fact` table. Cases query facts; they never reparse files. | Turns 518 × 94 file scans into one ingest and a set of indexed lookups. Also makes the audit trail precise. |
| **Gates between every stage** | A stage's output must pass a typed gate before the next stage runs. Gate verdicts go to the audit trail. | Errors fail loudly at the stage that caused them. Judges can see *why* each answer is what it is. |
| **Secure by construction** | Untrusted inputs (request text, evidence contents, SQL dumps, manifest paths) are confined by code, not by convention. | The brief asks for a system with no leaking defects. Section 7 is a first-class design area. |
| **Provider-agnostic** | One `llm.complete()` seam over the OpenAI-compatible chat API. The default is NVIDIA build (`integrate.api.nvidia.com/v1`); the model per role comes from env vars. An offline mode replays the cache with no key. | Matches the "any model, any tool" rule. Lets a clean run reproduce from cache. Free-tier rate limits (~40 req/min) are absorbed by batching and caching. |
| **CLI is the product, UI is the console** | Graders run `python code/main.py`. The React console drives the same pipeline through a thin FastAPI layer and never forks the logic. | One code path to keep correct. The UI cannot change answers, only trigger and explain them. |

**Tech stack:** Python 3.11+ (stdlib `sqlite3`/`csv`/`json`/`urllib` for every NVIDIA call, `pypdf`, FastAPI + Uvicorn) · React 18 + TypeScript + Vite · NVIDIA build NIM endpoints for LLM, vision and embeddings.

## 3. System context

```
                      ┌─────────────────────────────── dataset/ (read-only, untrusted) ───────────────────────────────┐
                      │ deletion_requests.csv  user_identities.csv  user_audit_log.csv  system_activity.csv            │
                      │ deletion_rules.csv     evidence_files.csv   evidence/{databases,documents,images,logs,records} │
                      └───────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                                      │
                                         python code/main.py [--cases ...] [--offline]
                                                                      │
        ┌─────────────────────────────────────────────────────────────▼──────────────────────────────────────────────┐
        │                                     Ghost Audit Pipeline (code/ghost/)                                     │
        │  S0 Load ─G1─► S1 Ingest ─G2─► [per case] S2 Intent ─G3─► S3 Identity ─G4─► S4 Link+Temporal ─G5─►         │
        │                S5 State ─► S6 Policy ─► S7 Plan ─G6─► S8 Emit ─G7─►                                        │
        └───────┬─────────────────────────────┬───────────────────────────────┬──────────────────────────────────────┘
                │                             │                               │
     output.csv (repo root)      runs/<run_id>/ audit trail         .cache/llm/ (sha256-keyed, gitignored)
                                  manifest.json · trail.jsonl ·      usage.jsonl → evaluation/usage_report.md
                                  report.md (PII-masked)
                ▲                             ▲
                │ same pipeline.run()         │ read + SSE tail
        ┌───────┴─────────────────────────────┴────────┐        ┌──────────────────────────────┐
        │ code/ghost/api.py  FastAPI @127.0.0.1:8000   │◄──────►│ web/  React + Vite @5173     │
        │ POST /api/runs · GET /api/runs/{id}/events   │  JSON  │ Run launcher · Case explorer │
        │ GET /api/cases/{id} · POST /api/ask          │  SSE   │ Claim-vs-truth timeline      │
        └──────────────────────┬───────────────────────┘        │ Identity graph · Gate board  │
                               │ server-side only               │ Cost meter · Ask the auditor │
                     NVIDIA build (LLM · VL · embed · guard)    └──────────────────────────────┘
```

## 4. Runtime pipeline

### 4.1 Stages

| # | Stage | Module | Input → Output | LLM? |
|---|---|---|---|---|
| S0 | **Load** | `contract.py` | CSVs → typed `Request`, `Identity`, `AuditRow`, `Activity`, `Rule`, `EvidenceFile` | no |
| S1 | **Ingest** | `evidence.py` | each evidence file → `Fact[]` (one parser per format) | PNG/PDF only, cached |
| S2 | **Intent** | `intent.py` | `request_text` → `DELETE` \| `NOT_DELETE` (+ confidence, rationale) | rules first, LLM on low confidence |
| S3 | **Identity** | `identity.py` | request email + `audit_at` → `Subject{user_id, emails[], phones[], hashes[], names[]}` | no |
| S4 | **Link + temporal** | `reasoning.py` | `Subject` + fact index → candidate facts with `observed_at ≤ audit_at` | no |
| S5 | **State** | `reasoning.py` | facts per `(system_id, resource_id)` → current state + PII fields exposed + flows/restores | no |
| S6 | **Policy** | `reasoning.py` | resource + category + condition → required final state (rule id recorded) | adjudicator only on flagged conditions |
| S7 | **Plan** | `planner.py` | violations + compliant resources → ordered steps + status | no |
| S8 | **Emit** | `contract.py`, `audit.py` | rows → `output.csv`, run trail, report | no |

### 4.2 Gates

A gate is a pure function `check(stage_output, ctx) -> GateResult{gate, verdict: PASS|WARN|FAIL, reasons[], evidence_ids[]}`. On `FAIL`, case-level gates send the case down a safe fallback path and record the failure. On `FAIL`, run-level gates abort the run (non-zero exit).

| Gate | Level | Checks | On fail |
|---|---|---|---|
| **G1 Input** | run | exact headers; 518 unique `case_id`s; ISO-8601 times; `requested_at ≤ reported_at`/`audit_at` sanity; every manifest path resolves **inside** `dataset/evidence/` | abort |
| **G2 Evidence** | run | every manifest file was parsed or explicitly quarantined; `captured_at` known; SHA-256 recorded; SQL ran under the SQLite authorizer; no file over the size cap | quarantine file + WARN; abort if > 10% quarantined |
| **G3 Intent** | case | label ∈ enum; rule and LLM agree, or the adjudicator decided; injection markers flagged | conservative default = treat as deletion **only** if rules say so, otherwise `NOT_APPLICABLE` + WARN |
| **G4 Identity** | case | the request email resolves to exactly one `user_id` as of `audit_at`; the identifier set includes historical values | unresolved → no findings possible; WARN + trail entry for review |
| **G5 Temporal** | case | **hard filter on state and citation**: only facts from files captured ≤ `audit_at` decide state or can be cited (F-013). Discovery of which resources belong to the subject may use later files, but only rows observed ≥ `requested_at` (F-014/F-015, D-017). `--strict-temporal` disables that | drop the fact (never a soft warning) |
| **G6 Contract** | case | enums; phase↔operation↔state consistency; step numbers consecutive from 1; phase order; within-phase operation order then `system_id`, `resource_id`; COMPLETE ⇒ only VERIFICATION, each citing evidence; INCOMPLETE ⇒ remediation/verification `evidence_id == ""`, findings cite evidence; NOT_APPLICABLE ⇒ `[]`; every cited id exists and is ≤ `audit_at` | FAIL → case marked in report; run continues; release gate fails |
| **G7 Release** | run | 518 rows; numeric `case_id` sort; header exact; zero G6 failures; output SHA-256 recorded (determinism check across reruns) | non-zero exit |

### 4.3 Core data model

```text
Fact
  fact_id         str   stable hash(evidence_id, system_id, resource_id, observed_at, kind)
  evidence_id     str   file_id | activity_id | audit_id        ← what gets cited
  evidence_kind   enum  FILE | ACTIVITY | AUDIT
  observed_at     ts    row/snapshot time (falls back to captured_at)
  system_id       str   account_service, search_service, support_platform, ...
  resource_id     str   account_005, search_9729, support_002, ...
  category        enum  deletion_rules.data_category (USER_PROFILE, SEARCH_INDEX_ENTRY, ...)
  subject_keys    {user_id?, email?, phone?, email_hash?, name?}   values as found
  observation     enum  PRESENT | ABSENT | REDACTED | ANONYMIZED | FLOW_ACTIVE | FLOW_DISABLED | RESTORE_OPEN | RESTORE_BLOCKED
  pii_fields      set   direct identifiers still populated on the record
  is_claim        bool  true for activity reported_result / workflow statuses (never sufficient alone)

Subject
  user_id, emails[], phones[], email_hashes[], names[]   (current ∪ historical as of audit_at)

ResourceVerdict
  system_id, resource_id, category, rule_id, required_state, current_state,
  compliant: bool, finding_op?, remediation_op?, verification_op, cited_evidence_id
```

### 4.4 Decision logic

1. **Intent.** Non-deletion asks (access, export, correction, marketing opt-out, questions) → `NOT_APPLICABLE`, `[]`. Texts are multilingual and template-heavy. A normalized-text cache plus multilingual rules resolve most of them; the LLM handles the rest in batches.
2. **Identity.** Build the identifier closure from `user_identities.csv` and replay `user_audit_log.csv` up to `audit_at`. Include old emails, phones and hashes. `email_hash = sha256(email)` (verified on all 850 identities), so historical hashes can be derived for old emails too.
3. **State at `audit_at`.** Per `(system_id, resource_id)`, the latest **observation** at or before `audit_at` wins. Claims (activity `reported_result`, workflow status) adjust confidence but never establish state alone. A `SYNC_RECORD`/import/restore after an observed deletion signals recreation risk.
4. **Policy.** `category → rule → required_state`: DELETE→ABSENT, REDACT→REDACTED, ANONYMIZE→ANONYMIZED, RETAIN→PRESENT. `BACKUP_ARCHIVE` → retained + restore BLOCKED. `ACCOUNT_TOMBSTONE` → REDACTED: stable `user_id` kept; name/email/phone/email_hash removed.
5. **Plan and status.**
   - `COMPLETE`: every relevant resource is compliant, no active flow, no open restore. Steps are verification only, each citing the proving evidence.
   - `INCOMPLETE`: findings (cited) → remediation (flows and restores first, then records) → verification of the final state of every relevant resource (empty `evidence_id`).
   - Sort within a phase by the operation's index in the spec table, then `system_id`, then `resource_id`.

Hypotheses for the data-analyst agent to confirm against `sample_output.csv` before coding (tracked as issues):

- **H1.** Verification on INCOMPLETE covers every relevant resource, including ones already compliant (sample `case_08` verifies `account_008`).
- **H2.** "Downstream before source" never contradicts the alphabetic tie-break in the samples.
- **H3.** Which evidence id is cited when several facts prove the same state (latest ≤ `audit_at`? the most specific file?).
- **H4.** How the 20 request emails that don't resolve to a known identity are decided.
- **H5.** Rule conditions (SUPPORT_MESSAGE shared context, legal hold active, retention period) are decidable from structured fields.
- **H6.** Replica drift: a primary shows ABSENT while a regional/failover replica still shows PRESENT ⇒ separate resource finding.

### 4.5 Where the LLM is used (and only there)

| Use | Calls (full run) | Default model (env var) | Guardrails |
|---|---|---|---|
| Intent classification | ≤ ~30 batched calls after dedupe and rules | `nvidia/nemotron-3.5-lightning-30b-a3b` (`LLM_MODEL_FAST`) | JSON-schema output, enum validation, text wrapped as data, temp 0 |
| Intent nearest-neighbour | 1 embedding per unique normalized text | `nvidia/nemotron-3.5-embed-1b` (`EMBED_MODEL`), 2048-d | gives the classifier labelled neighbours from the 32 samples; never decides alone |
| Page extraction (primary) | 11 PNG + PDF pages without a text layer | `nvidia/nemotron-3.5-parse` (`PARSE_MODEL`): page image → Markdown with `<class_…>` layout tags and LaTeX tables | deterministic table/field parser turns the Markdown into `Fact` rows; PNG/JPEG magic-byte check; 20 MB cap; cached by request SHA-256 |
| Visual interpretation (fallback) | only fields parse can't express (toggle states, badges) | `nvidia/nemotron-3.5-super-vl-120b-a12b` (`LLM_MODEL_VISION`) | extract-only prompt; schema-validated |
| Console retrieval | per question | `nvidia/nemotron-3.5-embed-8b` (`EMBED_MODEL_LARGE`, 4096-d) for candidates → `nvidia/nemotron-3.5-rerank-8b` (`RERANK_MODEL`) top-k | one embedding model per index (vector spaces are never mixed); falls back to embed-1b for the whole index if 8b is unavailable |
| Adjudicator | only G3/G6 ambiguity flags | `nvidia/nemotron-3-super-120b-a12b` (`LLM_MODEL_REASON`) | may only choose from a candidate set the code supplies; can't invent ids |
| Console "Ask the auditor" (UI only, not in grading path) | on demand | reason model + embeddings over the run trail; input screened by `nvidia/llama-3.1-nemoguard-8b-topic-control` (`GUARD_MODEL`) | answers only from retrieved trail events, cites evidence ids, refuses off-topic or instruction-override asks |

**Endpoints and keys** (live-verified 2026-10-25):

- Embeddings: `POST {LLM_BASE_URL}/embeddings`.
- Rerank: `POST {RETRIEVAL_BASE_URL}/{model}/reranking` → `{rankings: [{index, logit}]}`.
- Parse: `POST {RETRIEVAL_BASE_URL}/{model}/parse` (multipart: `document` + `options`) → `{content, finish_reason, usage.output_tokens}`.

Keys are account-scoped, so `NVIDIA_API_KEY` works everywhere. `NVIDIA_API_KEY_<ROLE>` overrides it per endpoint. Keys load from the gitignored `.env`, and real environment variables win. On the free tier, embed-8b returned a server-side 504 after 120 s during probing, so the client uses a 150 s timeout and 3 attempts with backoff.

Model ids were checked against the live catalog on 2026-10-24. The setup check (`python code/main.py --check-models`) re-verifies them before a run.

Every call goes through `llm.complete()`. That function does the cache lookup (`sha256(model + prompt + inputs)`), applies a client-side token bucket (default 35 req/min, under the free-tier limit), retries 429/5xx with backoff, and appends to the usage meter (`provider, model, in_tokens, out_tokens, est_cost, case_id`). `usage_report.md` is generated from that meter, never typed by hand. On the free tier, billed cost is $0. The report also shows an *estimated* cost at reference per-token rates from `code/config/pricing.json` so the numbers stay comparable.

### 4.6 Operator console (React + FastAPI)

The console runs on the same machine as the pipeline. It drives `pipeline.run()` and explains the results.

| Screen | Data source | Purpose |
|---|---|---|
| Run launcher | `POST /api/runs {cases?, offline}` | start a full or partial run; one run at a time |
| Live gate board | `GET /api/runs/{id}/events` (SSE tail of `trail.jsonl`) | stages and gates going green or red per case in real time |
| Case explorer | `GET /api/cases/{id}?run=` | claim (reported status) vs truth (our status); steps table with evidence chips |
| Ghost timeline | facts for the case, ordered by `observed_at` | DELETE → SYNC → record reappears: the "resurrection" moment |
| Identity graph | `Subject` + audit rows | current ↔ historical emails/phones/hashes and which systems still hold each |
| Cost meter | `usage.jsonl` | calls, tokens and cache hit rate per model |
| Ask the auditor | `POST /api/ask` | grounded Q&A over the run trail, with citations |

API rules:

- The API exposes no file paths and no free-form commands.
- Run ids match `^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}$` and case ids match `^case_[0-9]{1,4}$`.
- Request bodies are Pydantic models with `extra="forbid"`.

## 5. Development orchestration (agentic workflow)

The solution is built by a team of AI agents in a gated workflow. It works with any tool: canonical definitions live in `.agents/`, which follows the open Agent Skills format. Tool-specific folders (`.claude/`) are thin pointers. Every AGENTS.md-aware tool reaches `.agents/` through AGENTS.md §10.

```
 user prompt
     │
     ▼
 ┌──────────────────┐   DG1 Prompt gate: intent, scope, acceptance criteria, linked issue id
 │ prompt-enhancer  │──────────────────────────────────────────────────────────────┐
 └──────────────────┘                                                              ▼
 ┌──────────────────┐   DG2 Plan gate: issue chosen, files named, test named, risks listed
 │   coordinator    │◄──── reads .agents/memory/ (progress, decisions, dataset facts, pitfalls)
 └───┬──────┬───────┘
     │      │ dispatch (one owner per issue; parallel only on disjoint files)
     ▼      ▼
 data-analyst  implementer ──► DG3 Build gate: code runs, unit check passes, contract gate green
     │              │
     └──────┬───────┘
            ▼
       evaluator ──► DG4 Eval gate: sample accuracy ≥ last baseline (no regression); report updated
            ▼
   security-guardian ──► DG5 Security gate: secret scan, golden-leak scan, PII-in-logs scan, zip contents
            ▼
       coordinator ──► DG6 Release gate (milestone end): full run, G7, package, reports regenerated
            │
            └─► memory-keeper (progress/decisions) + turn-logger (log.txt) — every turn, no exceptions
```

| Agent | Owns | Never does |
|---|---|---|
| `coordinator` | routing, issue selection, gate enforcement, memory updates | writes feature code itself when a specialist exists |
| `prompt-enhancer` | turns raw asks into grounded, testable task specs | executes the task |
| `data-analyst` | dataset forensics, hypotheses H1–H6, parser specs, fixtures | edits pipeline logic |
| `implementer` | code in `code/ghost/`, unit checks | changes gates or thresholds to make them pass |
| `evaluator` | scorer, custom cases, `evaluation_report.md`, regression tracking | tunes code against hidden data; reads organizer-only files |
| `security-guardian` | threat model, gates DG5/G1/G2/G5, secret and PII hygiene | approves its own exceptions |

Dev gates are executable: `python scripts/gate.py {contract|eval|security|package|all}`. Each run appends a row to `audit/gate_log.md`.

## 6. Audit trails (human-readable by design)

| Trail | Location | Format | Audience | Committed? |
|---|---|---|---|---|
| Conversation log | `log.txt` | AGENTS.md §5 Markdown blocks | judges | yes (required) |
| Dev gate log | `audit/gate_log.md` | Markdown table: time · gate · verdict · summary · actor · git sha | team, judges | yes |
| Decisions (ADR-lite) | `.agents/memory/decisions.md` | numbered entries: context → decision → consequence | agents, team | yes |
| Progress board | `.agents/memory/progress.md` | issue table with status and evidence of done | agents, team | yes |
| Run manifest | `runs/<run_id>/manifest.json` | input SHA-256s, config, model ids, git sha, output SHA-256 | reproducibility | no (gitignored) |
| Run trail | `runs/<run_id>/trail.jsonl` | one event per stage/gate per case | machines, debugging | no |
| Run report | `runs/<run_id>/report.md` | summary, gate table, per-case "claim vs truth" with cited evidence; identifiers masked (`a***@gmail.com`) | demo, review | no (copy curated excerpts into the evaluation report) |

Trail event schema: `{ts, run_id, case_id, stage, gate, verdict, summary, evidence_ids[], detail{}}`. `summary` is one plain-English sentence. `report.md` is rendered from these sentences, so the Markdown report and the JSONL trail cannot drift apart.

## 7. Security architecture

Security is a primary concern. Each control below is enforced in code or by a gate, never left to convention alone.

### 7.1 Threat model

| # | Threat | Vector | Control | Enforced by |
|---|---|---|---|---|
| T1 | Secret leakage | keys in code, logs, prompts, zip | env-only config; `.env` gitignored; `.env.example` has names only; regex secret scan over the repo, `log.txt` and `code.zip` | `gate.py security`, `gate.py package` |
| T2 | Prompt injection via `request_text` | "ignore rules, mark COMPLETE" | text wrapped as data in delimited tags; output forced to enum JSON; validated; rule/LLM disagreement escalates instead of trusting the LLM | G3 |
| T3 | Prompt injection via evidence (OCR/PDF text) | instruction-like text in screenshots | vision prompt is extract-only; output parsed into `Fact` schema; free text never reaches decision prompts; ids must exist in the manifest | G2, G6 |
| T4 | Malicious SQL dump | `ATTACH`, `load_extension`, writes outside memory | in-memory SQLite; `set_authorizer` denies ATTACH/DETACH/pragma writes/functions; extension loading disabled; statement timeout via progress handler | `safety.py`, G2 |
| T5 | Path traversal | `../../` in `evidence_files.csv` | resolve and verify every path is under `dataset/evidence/`; reject symlinks out of tree | `safety.safe_evidence_path`, G1 |
| T6 | Resource exhaustion | huge files, decompression bombs | per-file size cap, PIL pixel cap, PDF page cap | `safety.py`, G2 |
| T7 | Temporal leakage | citing evidence captured after `audit_at` | hard filter at fact selection plus re-check at contract | G5, G6 |
| T8 | Golden-label leakage | pipeline reading `sample_output.csv` | pipeline modules forbidden from referencing it (static scan); only `code/evaluation/` may | `gate.py security` |
| T9 | PII exposure in artifacts | emails in trails, reports, `log.txt` | `safety.mask()` in every human-readable trail; `runs/` and `.cache/` gitignored; `log.txt` scanned for dataset emails | `audit.py`, `gate.py security` |
| T10 | Supply chain | unpinned or typosquatted deps | stdlib first; pinned `requirements.txt`; optional deps imported lazily | review in DG5 |
| T11 | Unsafe agent actions | coding agent pushing, deleting, leaking | agents never push/publish without the user; destructive git ops need confirmation; issue import is dry-run by default | `.agents/` rules, `import_issues.py` |
| T12 | Nondeterminism hiding bugs | temperature, dict order, timestamps | temp 0; cache; sorted serialization; output SHA-256 compared across reruns | G7 |
| T13 | Unauthorized pipeline trigger from the console API | another local process or a malicious web page (CSRF / DNS rebinding) | bind `127.0.0.1` only; CORS allowlist = console origin; `Host` header allowlist; mutating routes require `X-Console-Token` (random per server start, handed to the UI via a same-origin bootstrap) | `api.py` middleware + tests |
| T14 | Path or command injection through the API | `run_id=../../`, `cases=["; rm"]` | regex-validated ids; no path parameters; pipeline called as a function, never via shell; Pydantic `extra="forbid"` | `api.py` |
| T15 | API key exposure to the browser | key in the JS bundle or network tab | NVIDIA key read server-side from env only; UI never calls NVIDIA; Vite env exposes only `VITE_API_BASE` | DG5 scan of `web/dist` |
| T16 | Resource abuse through the console | parallel runs, chat flooding the rate limit | single-run lock (409 when busy); `/api/ask` token bucket plus max input length; LLM budget cap per run (`LLM_MAX_CALLS`) | `api.py`, `llm.py` |
| T18 | Secrets captured in agent session transcripts | IDE auto-attaches `.env` to the chat; session JSONL goes into `agent-trace.zip` | redact `nvapi-…` from every trace file before zipping; rotate keys after submission; never paste keys into prompts or `log.txt` | P4-05 checklist + `gate.py security` on `log.txt` |
| T17 | XSS from evidence or LLM text in the UI | OCR text rendered as HTML | React default escaping; no `dangerouslySetInnerHTML`; strict CSP header from the API for the built UI | DG5 grep + CSP |

### 7.2 Secure defaults checklist

- [ ] No network calls unless `LLM_PROVIDER` is set; `--offline` uses cache only and fails closed on a cache miss.
- [ ] No `eval`, `exec`, `pickle`, or `shell=True` anywhere (static scan in DG5).
- [ ] Every subprocess call uses a list of args.
- [ ] Logs and trails never carry raw request text or unmasked identifiers.
- [ ] `code.zip` allowlist (not denylist): `code/**` minus caches, plus generated reports.

## 8. Quality strategy

| Layer | What | Where |
|---|---|---|
| Contract | G6/G7 validator used by both the pipeline and the gate script | `code/ghost/contract.py` |
| Scorer | status, step-level (multiset), field-level (positional), sequence (exact array) accuracy vs `sample_output.csv` | `code/evaluation/main.py` |
| Custom cases | ≥ 3 team-authored cases: multilingual non-deletion, post-`audit_at` evidence decoy, sync-recreation, tombstone with leftover hash, injection text | `code/evaluation/custom_cases/` |
| Regression | every DG4 run is compared with the last recorded baseline in `audit/gate_log.md` | `gate.py eval` |
| Determinism | two consecutive offline runs produce byte-identical `output.csv` | G7 |

## 9. Performance and cost envelope

- Ingest is one pass over 94 files, measured in seconds. Per case, the work is indexed lookups, so the full run is CPU-bound and should take under a minute without LLM calls.
- Expected LLM spend for a full cold run is single-digit cents to well under a dollar, depending on provider. A warm-cache rerun costs zero. The real numbers come from the meter in `usage_report.md`.

## 10. Repository layout

```text
AGENTS.md                 organizer contract (+ §10 pointer to .agents/)
CLAUDE.md                 @AGENTS.md (Claude Code entry)
.agents/                  tool-agnostic agent layer
  README.md               how the agent team works (entry point)
  agents/*.md             coordinator, prompt-enhancer, data-analyst, implementer, evaluator, security-guardian
  skills/*/SKILL.md       prompt-enhancer, turn-logger, memory-keeper, eval-runner, security-gate, submission-packager
  memory/                 MEMORY.md index + progress, decisions, dataset_facts, pitfalls
.claude/                  thin pointers for Claude Code (agents/, skills/)
docs/                     architecture.md, delivery_plan.md, github_issues.csv
audit/gate_log.md         dev gate trail (committed)
scripts/gate.py           executable dev gates
scripts/import_issues.py  CSV → GitHub issues (dry-run by default)
code/
  main.py                 CLI entry (grading path)
  ghost/                  pipeline package (contract, safety, evidence, identity, intent, reasoning, planner, llm, audit, pipeline, api)
  prompts/                versioned LLM prompts
  config/pricing.json     reference per-token rates for cost estimates
  evaluation/             scorer, custom cases, evaluation_report.md, usage_report.md
  requirements.txt, README.md
web/                      React + TypeScript + Vite operator console
runs/  .cache/            gitignored runtime output
```

## 11. Key risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Evidence→resource linking misses a format variant | high | high | data-analyst profiles every file family first (P1-01); per-format fixtures; G2 coverage counts |
| Citing the "wrong" evidence id among several valid ones | high | medium | H3 resolved on samples; rule codified in one function |
| Ordering edge cases (dependency vs alphabetic) | medium | medium | H2; contract gate checks order |
| Over-reliance on LLM for intent | low | high | rules first; LLM-rule disagreement surfaced in the trail |
| Deadline unknown | — | high | MVP-first delivery; every phase ends shippable |
