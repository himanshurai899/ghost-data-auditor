# Verified dataset facts

Only verified facts belong here. Each has a `Verified by:` line. Hypotheses live in `docs/architecture.md` §4.4.

**F-001 — Volumes.** 518 requests; 32 samples (22 INCOMPLETE, 10 COMPLETE, 0 NOT_APPLICABLE); 850 identities; 306 audit rows (email 107, email_hash 107, phone 92); 4,011 activity rows; 15 rules; 94 evidence files (24 sql, 28 json, 26 log, 11 png, 4 pdf, 1 txt).
Verified by: `wc -l dataset/*.csv` + Counter over the CSVs (2026-10-24).

**F-002 — `case_id` order is numeric, not lexicographic.** Requests run `case_33` … `case_550` and appear in numeric order. Samples are `case_01` … `case_32` (zero-padded). Sort with `int(case_id.split('_')[1])`.
Verified by: `ids == sorted(ids, key=num)` True, `ids == sorted(ids)` False.

**F-003 — `email_hash = sha256(email)` (hex, as stored).** True for 850/850 identities, so historical hashes can be derived from historical emails.
Verified by: hashlib check over `user_identities.csv`.

**F-004 — All 518 request emails resolve once matching is case-insensitive.** Exact matching resolves 403 current and 95 historical. The other 20 are upper-case variants of stored emails: 15 current and 5 historical. Evidence files also contain 16 distinct upper-case emails, so lower-case on both sides. (Corrected 2026-10-25. The earlier "20 unresolvable" reading was an exact-match artefact.)
Verified by: exact vs `lower()` lookup over identities ∪ audit-log email values (data-analyst `intent.py`, P1-01); same result as identity work #16 / PR #55.

**F-005 — `reported_status` mix.** COMPLETE 254 · PARTIALLY_COMPLETE 152 · NOT_STARTED 112.

**F-006 — Activity `reported_result` mix.** SUCCESS 2914 · FAILED 721 · PARTIAL 376. Event types include DELETE_RECORD 890, UPDATE 672, SYNC 447, INDEX 400, SEND_EMAIL 368, REFRESH_CACHE 284, RETAIN 206, ANONYMIZE 204, REDACT 173, CREATE_EXPORT 155, CHECK_DATA_FLOW 89, DISABLE_DATA_FLOW 36, BLOCK_RESTORE 36, CHECK_RESTORE_ACCESS 28, LINK_RESOURCE_IDENTITY 12, CLASSIFY_REQUEST 10, RESTORE_BACKUP 1.

**F-007 — Within-phase order is the spec table's operation order, then `system_id`.** Sample case_03 verification: ABSENT(account_service) → PRESENT(security_service) → ANONYMIZED(analytics_platform). Operation order wins over system_id.
Verified by: sample_output.csv case_03.

**F-008 — INCOMPLETE verification covers already-compliant resources too.** Sample case_08 verifies `account_008` ABSENT although only `export_001` had a finding. All INCOMPLETE remediation and verification steps carry `evidence_id=""`.
Verified by: sample_output.csv case_08, case_10.

**F-009 — SQL snapshots share a common schema.** Tables include snapshot_scope, customer_profiles, customer_search_documents, customer_analytics_profiles, support_records, customer_exports, connector_subscriptions, backup_restore_entries, security_audit_records, plus replica-specific tables (read/regional/reporting/failover). `customer_reference` holds `user_NN`.
Verified by: `grep "CREATE TABLE" dataset/evidence/databases/*.sql`.

**F-010 — Logs are `key=value` lines** with `service`, `event`, `resource_id`, `lookup_key` (an email or user_id) and state hints (`rows=`, null identifier fields = anonymized).
Verified by: head of resource_lookup_trace_*.log and support_replica.log.
Refined by F-017: there are four log groups and six envelope syntaxes.

Facts F-011 to F-022 come from P1-01 (#10). Parser and decision detail is in `docs/evidence_field_map.md`. The scratch scripts named below were run with the project venv; they live in the session scratchpad and are not committed.

**F-011 — Within-phase order is `(phase, spec-table operation index, system_id, resource_id)` with no dependency reordering.** It reproduces step order and consecutive `step_no` for 32/32 samples. In remediation, account_service is deleted before search_service (case_16, case_24), so "downstream first" is never applied.
Verified by: `check.py` sorted each sample's steps with that key and compared to sample_output: 32/32 identical.

**F-012 — Evidence-id selection.** Remediation steps and INCOMPLETE verification steps use `""`. A cited step uses the latest file with manifest `captured_at` ≤ `audit_at` (inclusive) that holds an explicit row for the resource in the cited state: 70 of 75 cited steps, plus case_07 → evidence_58, which needs the PDF. For ABSENT with no explicit row, cite the latest table-level snapshot of that system (SQL table or JSON snapshot collection, empty allowed) at or before `audit_at` whose file has at least one data row. That covers 4 of 75: case_01, case_02 and case_04 → evidence_54, and case_31 → evidence_51. Lookup logs and ledgers never prove an omission. No sample cites an activity_id or audit_id.
Verified by: `evid.py` over all 75 cited steps; no counter-example.

**F-013 — The manifest `captured_at` decides citability, not the row time.** case_09: evidence_06 has a backup_4978 row observed 3 minutes before `audit_at`, but the file was captured 2 days later; the sample cites evidence_93. Cases 21 to 30 never cite evidence_02 (captured 2026-09-17, rows stamped ≤ 09-15). The bound is inclusive: evidence_51 is captured exactly at `audit_at` and is cited by case_31 and case_32.
Verified by: sample_output case_09, case_21–30, case_31, case_32 against evidence_files.csv.

**F-014 — Discovery uses identifier links observed at or after `requested_at`; earlier links are decoys.** "Resource has an identifier link to the subject observed ≥ requested_at" ⇔ "resource is in the expected steps" held for 86/86 (case, resource) links. The three pre-request links are all excluded by the samples: case_07 object_19, case_17 tombstone_17 and case_17 account_6523.
Verified by: `prereq2.py` over the 32 samples.

**F-015 — Discovery may use rows from files captured after `audit_at`; state may not.** Eight expected resources are linked only via late files: case_09 account_3960 and audit_record_4902 (evidence_06); case_23, case_24, case_29 and case_30 audit records, case_26 account_5684 and case_27 account_3866 (evidence_02). The late files also contradict the answer: evidence_02 shows account_3866 ACTIVE on 09-17, while case_27 verifies it ABSENT from evidence_92. G5 must filter state and citation, not identity linking.
Verified by: `prereq2.py` late-link scan; sample_output case_27.

**F-016 — Replica drift is always "account row only in the replica table".** In all 15 primary/replica table pairs across 12 SQL files, the differences are replica-only account rows. No row differs field by field. A replica-only row yields REPORT_REMAINING_RECORD on `account_service/<same resource_id>`; the replica is not a separate system. Example: case_05 account_005 (evidence_54, failover). In every sample case, a SYNC_RECORD to the replica follows the failed or successful DELETE: case_05 activity_3483, case_16 activity_3577, case_24 activity_3608.
Verified by: `drift.py` over all SQL; sample_output case_05, case_16.

**F-017 — Text evidence families.** SQL (24): inventory ×11 (typed tables + `snapshot_scope`), read replica ×5, regional ×3, reporting ×2, failover ×1 (these use generic `record_json` tables), accounts failover ×1, search primary ×1. JSON (28): snapshot bundle ×12, service_resource_export ×11, three ledger-shaped files, analytics report ×1, export jobs ×1. LOG (26): readback traces ×11 (`trace_id`-paired started/completed lines), platform traces ×12 in six envelopes (kv, JSON, syslog, bracket, pipe, cloud `message=`), ledger logs ×2, support_replica ×1. TXT (1): handover ledger. The subject key is often only on the `*_started` line, so join on trace id. `cache_lookup result=miss` lines share the trace and are not state.
Verified by: extractor `extract.py` parsed every text file (3,236 resource rows); every manifest file except the 11 PNG and 4 PDF yields rows.

**F-018 — Activity `reported_result` does not predict DELETE outcomes, and activity is never cited.** DELETE_RECORD SUCCESS rows were still PRESENT in 5 sample resources (for example case_10 support_002, case_24 account_5334). FAILED rows were verified ABSENT in 3 COMPLETE cases (case_25, case_26, case_28 accounts). ANONYMIZE/REDACT results agree with the expected state 22/22; CHECK_DATA_FLOW → ACTIVE 6/6; CHECK_RESTORE_ACCESS → RESTORE_RISK 3/3. `details` text never names a subject, except on the 12 LINK_RESOURCE_IDENTITY rows.
Verified by: `acts.py` cross-tab of activity rows vs expected sample operations.

**F-019 — LINK_RESOURCE_IDENTITY rows bridge images and PDFs.** Each of the 12 rows is stamped exactly 7 minutes after the manifest time of one PNG or PDF, for example activity_4000 ↔ evidence_04 and activity_4011 ↔ evidence_42. The PDFs have text layers: evidence_58 names support_001 and is cited by case_07.
Verified by: activity times vs evidence_files.csv; pypdf text extraction of the four PDFs; one PNG viewed (evidence_04).

**F-020 — Resource-linking ceiling.** 28 of the 111 expected (case, resource) pairs have no identifier link in text evidence:

- 14 accounts appear only in a deletion_worker activity row;
- 10 account or analytics rows carry only null identifiers (plus an activity row);
- 1 is linked only through a PDF (case_07 support_001);
- 3 appear in no participant file at all: case_04 account_004, case_18 audit_record_6645, case_20 audit_record_5569.

Deletion batches run once a day and interleave subjects, so a time window alone cannot pick the account: an elimination heuristic matched only 5/32.
Verified by: `counts.py`, `link2.py`; a full-text search for the three missing ids found them only in sample_output.csv.

**F-021 — Ten requests are non-deletion: case_533 … case_542, all NOT_STARTED.** They cover a phone or email change, a surname fix, marketing opt-out (case_538 says "remove me from marketing lists only"), data download or copy, access, invoices and login help. Most contain a negated or scoped deletion verb. There are also exactly 10 CLASSIFY_REQUEST ("non-deletion") activity rows. No sample is NOT_APPLICABLE.
Verified by: `intent2.py` first-sentence and negation scan of deletion_requests.csv; grep CLASSIFY_REQUEST.

**F-022 — Policy conditions are fixed by category in this dataset.** Every SECURITY_AUDIT_LOG `retention_until` is between 2031-12-31 and 2034-09-30, which is after every `audit_at`, so these records are always RETAIN → VERIFY_RECORD_PRESENT (17 INCOMPLETE and 7 COMPLETE samples). Every SUPPORT_MESSAGE is REDACT and every SUPPORT_ATTACHMENT is DELETE (case_13 support_4218). An analytics `contact_lookup email_opt_in=true` row is DELETE, not ANONYMIZE (case_12 analytics_9914). No sample covers a legal hold.
Verified by: min/max scan of `retention_until`; `check.py` op-chain table over sample_output.
