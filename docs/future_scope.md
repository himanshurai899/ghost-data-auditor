# Future scope (P5)

Status: design notes, nothing here is built · Backlog: #47-#51 (P5-01..P5-05) · Related: [architecture.md](architecture.md), [console_api.md](console_api.md), [delivery_plan.md](delivery_plan.md) §7

Audience: engineers and judges deciding what to build next. Every "reuses" claim names a module that exists in `code/ghost/` today.

## 0. Known limits of the current system

Read this first. Each item below bounds what the future work can honestly promise.

- **Three sample resources appear in no participant file.** case_04 `account_004`, case_18 `audit_record_6645`, case_20 `audit_record_5569` are found only in `sample_output.csv` (`.agents/memory/dataset_facts.md` F-020). No parser can recover them; audit records have no activity row.
- **Orphan linking is partial.** `orphan.py` places resources that carry no identifier by using the daily deletion-batch structure in `system_activity.csv`. On the sample set it recovers 10 of 28 unlinkable (case, resource) pairs, with precision 10/11. On hold-out accounts it recovered 44 of 98 with 3 wrong. Accounts in ties of three or more candidates are skipped on purpose. These are heuristics fitted to this generator, not a general method.
- **Sample score ceiling.** Status accuracy 0.969, step F1 0.957, sequence (exact `steps_json` match) 0.656, 21 of 32 cases (`code/evaluation/evaluation_report.md`). The 11 non-exact cases are the missing ids above, six COMPLETE cases with an ambiguous analytics owner, and batch ties. The remaining gap is not closable from participant data.
- **Reliance on the activity-batch structure.** R1-R3 in `orphan.py` assume one daily worker run, account first, then a chain with a fixed 7 or 19 minute gap. A real platform without that regularity gets no orphan linking at all.
- **No live connectors.** Ingest reads frozen files in `dataset/evidence/` (`evidence.ingest`). Nothing queries a running system.
- **No write access to any system.** The auditor reports and plans; it never deletes, redacts or disables anything. `planner.plan` emits steps as data.
- **Trail is not tamper-evident.** `audit.Trail` appends masked JSON lines to `runs/<id>/trail.jsonl`; `manifest.json` holds `git_sha`, input hashes and `output_sha256`, but events are not chained or signed.
- **Late-evidence rule is a judgment call** (D-017): files captured after `audit_at` may reveal membership but never state or citations; `--strict-temporal` disables even that.

## 1. Continuous deletion assurance (stream mode) — #47

**Problem.** A batch audit is a snapshot. A sync or restore can recreate data an hour after the audit passed, and nobody looks again.

**Design.**

```text
 deletion events ──► queue ──► trigger(case, t0)
 (workflow, API)                  │
                                  ▼
 connector/snapshot ──► evidence.ingest ──► Fact store (append-only, indexed)
                                  │
   schedule: T+0, +1h, +24h, +7d  ▼
                       reasoning.link/evaluate ──► planner.plan ──► status
                                  │                                  │
                                  └── diff vs last status ──► alert ─┴─► Trail
```

A deletion event opens a watch on the subject. The auditor re-runs the existing per-case path (`pipeline.audit_case`) at fixed offsets and on every new fact for a watched subject. A COMPLETE-to-INCOMPLETE transition raises an alert carrying the new `REPORT_REMAINING_RECORD` / `REPORT_ACTIVE_DATA_FLOW` / `REPORT_RESTORE_RISK` findings (a "resurrection").

**Reuses.** `audit_case` is already a per-case function with its own gates; `identity.resolve` takes `audit_at`, so "now" is just `audit_at = now`; `Fact.observed_at` / `captured_at` already separate row time from capture time (G5); the `Trail` event shape is the alert payload; the console's SSE route (`GET /api/runs/{id}/events`) already streams trail events.

**Must change.**
- `pipeline.run` is batch and file-oriented (`requests_path`, one `output.csv`). Extract a `watch(case, as_of)` entry point and a persistent store of the last verdict per case.
- Facts must be incremental. `evidence.ingest` re-reads everything; it needs a keyed upsert and a cursor per source.
- `orphan.py` assumes the whole `system_activity.csv` is in hand; in a stream it must run on a sliding window or be disabled.
- The "watch window" and re-check schedule are new configuration.

**Security.** Alerts must go through `safety.mask_text` like trails (T9). Event intake is a new trust boundary: authenticate producers, validate against a schema, never accept a `case_id` that skips the G1 checks. Read-only credentials only. Rate-limit re-runs per subject so an event flood cannot become an LLM bill (T16 budget cap still applies).

**Rollout.** (1) Replay mode: feed `system_activity.csv` in time order to a watcher and check it flags known resurrections. (2) Shadow mode on one real system, alerts to a log only. (3) Alerts to on-call.
First milestone, about 4 days: a `watch` entry point, a persisted verdict store, and the replay harness over the dataset, with one test that a SYNC_RECORD after a verified deletion flips a case to INCOMPLETE.

**Risks.** Alert fatigue from stale snapshots; claims replayed out of order; cost of repeated full ingests.

**Success.** Time from recreation to alert (median, p95); false-alert rate over a month of shadow mode; zero missed resurrections in replay.

## 2. Live read-only connectors — #48

**Problem.** Snapshots are stale by construction and are exported by someone else. A regulator wants the state of the system now.

**Design.** One adapter per system, each implementing the contract the file parsers already implement: `fetch(subject_keys, as_of) -> (list[Fact], list[Coverage])`, mirroring `parse(path, meta) -> (facts, coverage)` in `evidence.py`.

```text
 Subject (identity.resolve) ──► for each connector:
    PostgresAdapter   SELECT ... WHERE email=? / user_id=?   ─┐
    SearchAdapter     term query on keyed fields (ES/OS)      │
    S3Adapter         list_objects + head_object, tags        ├─► Fact[] + Coverage[]
    ZendeskAdapter    users/tickets search, attachments       │       │
    SegmentAdapter    user/profile API, destinations          ─┘       ▼
                                                          evidence.ingest / G2
```

Mapping rules follow `docs/evidence_field_map.md`: row present maps to `PRESENT` with `pii_fields` listing populated direct identifiers; a keyed lookup that returns nothing maps to `ABSENT` only when the adapter can claim table-level `Coverage` (what F-012 requires today for omission); otherwise it produces no fact. An API response is a claim about a live system, so adapters stamp `captured_at = now` and a new `evidence_id` per fetch that is stored (a content hash plus the response body, masked) so findings stay citable later.

**Reuses.** `Fact`, `Coverage`, `system_for`, `norm_keys`, `is_null`; `reasoning.link/evaluate` and `planner.plan` need no change; G2 quarantine already isolates one failing source; `llm.Client`'s on-disk cache pattern (sha256 of request) is the model for response snapshots and offline replay.

**Must change.**
- Evidence ids today are manifest `file_id`s. Live reads need a stored, immutable evidence record per fetch, otherwise findings cite something that no longer exists.
- Discovery is currently global (every file scanned). Live adapters query by identifier, so the identifier closure from `identity.resolve` must be complete up front; historical emails matter even more.
- Backup and restore-path facts (`RESTORE_OPEN`/`BLOCKED`) and data flows need their own sources (backup catalog, sync job config); none of the five named systems expose them directly.
- `is_claim` handling for API-reported states.

**Security.** This is the highest-risk item for data exposure. Dedicated read-only roles per system (Postgres `SELECT` on named views only; S3 `ListBucket`/`GetObjectTagging`, no `GetObject` of bodies; Zendesk read-only token; Segment read scope). Credentials from the environment or a secret manager, never the repo (T1). Parameterized queries only (T14). Never persist raw PII: store hashes and `pii_fields` names, not values. Egress allow-list per adapter. SSRF guard on any URL taken from data (T5 analogue). The audit identity itself needs its access logged.

**Rollout.** Postgres first (closest to `ev_sql.py`), then S3, then search, then Zendesk and Segment. Run each in shadow beside the snapshot path and diff the facts.
First milestone, about 5 days: adapter interface plus a Postgres adapter against a local test database seeded from a sample SQL export, producing Facts that match `ev_sql.parse` on the same data.

**Risks.** API rate limits and pagination; eventual consistency (search index lags the primary, which is exactly the drift this audit looks for); load on production databases; accidentally reading more PII than needed.

**Success.** For each adapter, fact-level agreement with the snapshot path on the same instant; query cost and latency per subject; zero values of direct identifiers in stored evidence.

## 3. Policy as code and jurisdiction packs — #49

**Problem.** `deletion_rules.csv` has 15 rows keyed by data category and condition. The lookup is `reasoning._policy(category, rules)`. It cannot express jurisdiction, legal basis, retention clocks or exceptions, and rule changes are not versioned or tested.

**Design.** A small declarative DSL (YAML or JSON, parsed with a strict schema) compiled to the same decision the code makes today: `(category, conditions) -> (action, required_state, rule_id)`.

```text
 policy/
   base.yaml            categories, actions, state mapping (DELETE->ABSENT, ...)
   packs/gdpr_art17.yaml   deadlines, exceptions (legal claims, Art. 17(3))
   packs/ccpa.yaml        retention exceptions, 45-day clock
   packs/dpdp.yaml
   tests/*.yaml         (resource facts, jurisdiction) -> expected verdict
 subject.jurisdiction ──► policy.resolve(pack, version) ──► rules[] ──► reasoning.evaluate
```

Each verdict records `rule_id`, `pack` and `version`, so a receipt can say which law and which revision produced it. Packs inherit from `base` and may only tighten or add exceptions that are declared explicitly.

**Reuses.** `ResourceVerdict` already carries `rule_id`, `required_state`, `category`; `reasoning.evaluate(facts, rules, audit_at, ...)` takes `rules` as a parameter, so the DSL can feed it the same shape; `planner.plan` is untouched. The 32 samples are the regression suite: the base pack compiled from the CSV must reproduce current output byte for byte (the G7 SHA-256 check).

**Must change.** Subject jurisdiction does not exist in the data (`user_identities.csv` has none): it must come from the request or the account. Time-based conditions (retention periods, response deadlines) require evaluating against `audit_at`, which `_policy` does not do today (retention is treated as within period, D-016 H5). Legal-hold behavior is an open question (no sample covers it). Rules currently map to one output state; a pack may require a different operation ordering, which the fixed spec-table key in `contract.finalize_steps` does not allow.

**Security.** A policy is code that decides what gets deleted. Packs are signed or reviewed commits; the loader rejects unknown keys and any expression language (no `eval`, T-series static scan stays). The active pack and version are recorded per run. Legal interpretation must be owned by counsel, not the engineer who writes the YAML; the tool must not claim legal compliance.

**Rollout.** (1) Compile the CSV to the DSL and prove equivalence on all 518 rows. (2) Add policy tests. (3) Add one pack (GDPR) with a deliberately small exception set, reviewed by legal. (4) Add CCPA and DPDP.
First milestone, about 3 days: schema, loader, CSV-to-DSL converter, equivalence test (identical `output.csv` hash).

**Risks.** Laws are interpreted, not computed; false precision is worse than none. Pack drift across jurisdictions for the same person. Over-engineering a DSL for 15 rules.

**Success.** Byte-identical output for the base pack; every rule has at least one positive and one negative test; a rule change shows up as a diff in tests, not as a surprise in production.

## 4. Signed, hash-chained audit receipts — #50

**Problem.** A completion certificate is only worth something if no one can edit the evidence behind it. Today `trail.jsonl` is an editable text file.

**Design.**

```text
 Trail.event ──► e_i = {..., prev: H(e_{i-1})}   (hash chain, per run)
 Trail.close ──► manifest.json {chain_head, output_sha256, inputs{...}, git_sha}
 receipt(case) = { case_id, status, steps_sha256, evidence hashes cited,
                   policy pack+version, chain_head, run_id, issued_at }
 signature = Ed25519(receipt_canonical_json, key)   (detached .sig)
 verify(receipt, sig, trail.jsonl, evidence files) ──► OK | which link broke
```

Chaining makes insertion, deletion or reordering of any event detectable. Signing the receipt binds the verdict to the chain head and to the hashes of the exact evidence files cited.

**Reuses.** `audit.Trail` is the single writer of events (D-007: JSONL and Markdown from the same events); `pipeline.run` already writes `output_sha256` and `inputs` hashes into `manifest.json` and `pipeline.sha256_file` hashes files; G7 already requires byte-identical reruns, which gives reproducible `steps_sha256`; `safety.mask_text` already scrubs events before they are written, so the chain covers the masked form and no receipt ever carries PII.

**Must change.**
- Add `prev`/`hash` to `Trail.event` and the chain head to the manifest. `render_report` must tolerate the extra fields.
- Events contain a wall-clock `ts` and a random `run_id`; the chain is tamper-evident but not reproducible across reruns. That is fine for a receipt, but the determinism check in G7 must hash `output.csv`, not the trail.
- Evidence hashes: the manifest hashes only three input files today. Cited evidence files need a per-file hash recorded at ingest (G2 already has the bytes).
- Key handling: signing key outside the repo, loaded from the environment (T1), with rotation and a public-key registry. A trusted timestamp (RFC 3161) is needed to bind `issued_at`; a local clock is not proof.
- A `verify` CLI and a console view of it.

**Security.** The signature proves integrity and origin, not truth: a receipt over wrong findings is a signed wrong answer. State that on the certificate. Protect the key (KMS/HSM for production, never in the console process). Receipts must not include masked-away values. Avoid custom crypto: use a vetted library for Ed25519 and SHA-256.

**Rollout.** (1) Chain only, with `verify`. (2) Per-file evidence hashes. (3) Signing with a local key. (4) External timestamp and key registry.
First milestone, about 3 days: chained `Trail`, `verify` that detects a flipped byte or a deleted line, and a test for both. Signing follows.

**Risks.** Key compromise; a chain over already-wrong data; log truncation at the tail (needs an externally anchored head); regulators may not accept home-grown formats.

**Success.** 100% of tamper tests (edit, delete, reorder, truncate) detected; `verify` runs on a cold machine from only the receipt, trail and evidence; external review of the format.

## 5. Human-approved auto-remediation — #51

**Problem.** The planner already produces an ordered, safe list (`DISABLE_DATA_FLOW`, `BLOCK_RESTORE`, then `DELETE_RECORD`/`REDACT_RECORD`/`ANONYMIZE_RECORD`, then verification). Executing it by hand is slow and error-prone.

**Design.** Each remediation operation maps to an approved runbook; a human approves a specific plan; an executor runs it; the auditor re-checks.

```text
 planner.plan ─► plan(case) ─► approval queue ──(approver, 2nd person for DELETE)──┐
                                                                                    ▼
   verify (pipeline re-run, fresh facts) ◄── executor: runbook(op, system, resource)
        │                                          │ dry-run diff first
        └── pass: receipt (§4)      fail: stop, roll back or escalate, never auto-retry destructive ops
```

Runbooks are versioned, per `(system_id, operation)`, idempotent, and declare a dry-run that prints exactly what would change. Steps run strictly in the planner's order; a failure halts the plan.

**Reuses.** `planner.plan` output (the step contract is already the runbook index); the planner's `finalize_steps` ordering guarantees flows and restores are handled before records; verification steps already name the expected final state, so `VERIFY_*` becomes the post-condition of each runbook; the console API and UI give the approval surface (add routes next to `POST /api/runs`, protected by the existing `X-Console-Token` model, T13).

**Must change.**
- Everything is read-only today. This is the first write path and needs its own process, identity and credentials, separate from the auditor.
- A plan identity: approvals must bind to the plan hash (`steps_sha256` from §4) so a plan changed after approval is rejected.
- Verification must use fresh facts (connectors from §2), not the same snapshot that produced the plan. Without live connectors this item cannot close the loop.
- A rollback or quarantine story: soft-delete with a hold window before purge; backups cannot be edited, so `BLOCK_RESTORE` is the only action there.
- Roles, approver separation of duties, and an immutable record of who approved what (§4).

**Security.** Default is no write access at all; the executor is a separate service with per-system, per-operation least-privilege roles (for example, delete only on the named table or prefix, no `DROP`). Two-person approval for `DELETE_RECORD` and for anything touching retained categories; the planner must never schedule a delete for a retain-required record, and the executor re-checks the rule at execution time (not just at plan time) because state may have changed. No LLM output ever reaches an executor; runbook parameters come only from validated `Fact` fields (T2, T3, T14). Kill switch, rate limits and a blast-radius cap per run. Full audit trail for every action.

**Rollout.** (1) Dry-run only: render what each runbook would do and diff it against the plan. (2) Execute `DISABLE_DATA_FLOW` and `BLOCK_RESTORE` first (reversible) in a staging system. (3) Redact and anonymize. (4) Delete, last, with the approval and hold window.
First milestone, about 5 days: runbook interface, dry-run executor for one system (support platform redaction), plan-hash approval record, and an end-to-end test on a fake system that runs plan, approve, execute, re-audit and gets COMPLETE.

**Risks.** Deleting data that policy requires to be retained (the worst failure); partial execution leaving a worse state; approval rubber-stamping; stale plan after state changed; runbook drift.

**Success.** Zero out-of-policy deletions in staging; every executed step has an approval and a passing post-check; reduction in median time from INCOMPLETE finding to COMPLETE re-audit.

## 6. Prioritized roadmap

| Priority | Item | Why now | First milestone | Depends on |
|---|---|---|---|---|
| 1 | Signed, hash-chained receipts (#50) | Smallest change (one class, `audit.Trail`), no new access, and everything else needs it for accountability | ~3 days: chained trail + `verify` | none |
| 2 | Policy as code (#49) | Removes the CSV limit; equivalence is testable against existing output | ~3 days: DSL + equivalence test | none |
| 3 | Live read-only connectors (#48) | Unlocks real use; highest exposure, so read-only and staged | ~5 days: adapter interface + Postgres | 1 for evidence records |
| 4 | Continuous assurance (#47) | Only valuable on fresh facts; replay mode can start earlier | ~4 days: `watch` + replay harness | 3 (live), 1 |
| 5 | Auto-remediation (#51) | First write path, highest risk; needs approvals, receipts and fresh verification | ~5 days: dry-run executor + plan-hash approval | 1, 3 (and 2 for retain rules) |

Items from `docs/delivery_plan.md` §7 not covered here (lineage graph, multi-tenant SaaS, evaluation at scale) remain unscoped.
