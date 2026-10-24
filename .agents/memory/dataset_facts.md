# Verified dataset facts

Only verified facts belong here. Each has a `Verified by:` line. Hypotheses live in `docs/architecture.md` §4.4.

**F-001 — Volumes.** 518 requests; 32 samples (22 INCOMPLETE, 10 COMPLETE, 0 NOT_APPLICABLE); 850 identities; 306 audit rows (email 107, email_hash 107, phone 92); 4,011 activity rows; 15 rules; 94 evidence files (24 sql, 28 json, 26 log, 11 png, 4 pdf, 1 txt).
Verified by: `wc -l dataset/*.csv` + Counter over the CSVs (2026-10-24).

**F-002 — `case_id` order is numeric, not lexicographic.** Requests run `case_33` … `case_550` and appear in numeric order. Samples are `case_01` … `case_32` (zero-padded). Sort with `int(case_id.split('_')[1])`.
Verified by: `ids == sorted(ids, key=num)` True, `ids == sorted(ids)` False.

**F-003 — `email_hash = sha256(email)` (hex, as stored).** True for 850/850 identities, so historical hashes can be derived from historical emails.
Verified by: hashlib check over `user_identities.csv`.

**F-004 — 20 of 518 request emails match no current or historical email.** These are candidates for NOT_APPLICABLE, unknown subjects, or matching on other keys. Resolve under H4.
Verified by: set membership vs identities ∪ audit-log old values.

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
