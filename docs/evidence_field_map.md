# Evidence field map: parser spec and decision rules

Owner: data-analyst · Issue: P1-01 (#10) · Verified against `dataset/sample_output.csv` (32 cases) on 2026-10-25.
Consumers: P1-05/P1-06 parsers, P1-10 state, P1-11 policy, P1-12 planner.

Every rule here was checked against the samples, or it is marked **open**. Identifiers in examples are masked (`<email>`, `<phone>`, `<hash>`, `<name>`). People are referred to by `user_id`, records by `resource_id`. Facts are numbered in `.agents/memory/dataset_facts.md` (F-011 and up) and the hypothesis verdicts are in `decisions.md` D-016.

---

## 1. Rules that apply to every parser

### 1.1 System from resource prefix

Use the record's own `system` field when it has one; ledger rows always do. Otherwise derive the system from the `resource_id` prefix:

| prefix | system_id | prefix | system_id |
|---|---|---|---|
| `account_` | account_service | `backup_` | backup_service |
| `search_` | search_service | `data_flow_` | integration_service |
| `support_` | support_platform | `audit_record_` | security_service |
| `analytics_` | analytics_platform | `tombstone_` | identity_service |
| `export_` | export_service | `legal_hold_` | legal_service |
| `marketing_` | marketing_platform | `object_` | object_storage |

Replica tables are not separate systems. A row in `customer_profiles_failover_replica` or `customer_data_read_replica` is still `account_service/<id>` (F-016).

The JSON `data_store` value can be misleading. Snapshot-bundle collections named `operational_record_history` sit under the stores `backup_restore_service`, `privacy_treatment_service` and `support_storage_service`, but each record has its own `system` field, and that field is the one to use.

### 1.2 Identifier normalisation (subject keys)

| key | normalise | appears as |
|---|---|---|
| email | lower-case before matching. Upper-case emails exist in requests (20 of 518) and in evidence (16 distinct values) | `email`, `owner_email`, `customer_email`, `requester_email`, `uploaded_by`, `lookup_key`, `match_key`, `subject_key`, `scan_key`, `owner_key`, `correlation_key`, `matched_value`, `lookup_value`, `subject_reference`, `subject_selector`, `query`, `document.email`, free text in `message_text` |
| user_id | as is (`user_\d+`) | `user_id`, `customer_reference`, `subject_reference`, `subject_ref`, `subject_selector`, `lookup_key`, `correlation_key` |
| email_hash | lower-case hex, 64 chars. Equals sha256(email) | `email_hash`, `correlation_key` (for example analytics_9914, evidence_01) |
| phone | digits only | `phone`, `owner_phone`, `requester_phone`, `scan_key`, `matched_value` |
| name | display only. Never a link key, because evidence_54 and evidence_57 hold look-alike decoy names | `full_name`, `name`, `display_name`, `requester_name` |

Null tokens: JSON `null`, SQL `NULL`, the string `"null"` in logs, `""`, and `"[REDACTED]"`. Treat all of them as "field not populated".

### 1.3 Time

- `observed_at` precedence: row field (`observed_at`, `recorded_at`, `updated_at`, `indexed_at`, the log line timestamp) → snapshot `captured_at` → manifest `captured_at`.
- **Citable** means the manifest `captured_at` is at or before `audit_at`, inclusive. The file's capture time decides this, not the row time (F-013).
- **State** at `audit_at` uses citable facts only.
- **Discovery** (which resources belong to the subject) may also use rows from files captured later, but only rows observed at or after `requested_at` (F-014, F-015).

### 1.4 Observation vocabulary (signal → `Fact.observation`)

| observation | signals (any one is enough) |
|---|---|
| PRESENT | `rows=1`, `http_status=200`, `status_code: 200` with a `profile` object, `result=hit`, `total_hits>=1`, `hits.total>=1`; ledger `FOUND`/`IDENTIFIABLE`; a SQL/JSON row exists; `account_status` `ACTIVE`/`DELETION_PENDING`; `download_available`/`available` true; `marker_found=false` with `rows=1` |
| ABSENT | `rows=0`, `http_status=404`, `status_code: 404`, `profile: null`; ledger `NOT_FOUND`; **omission** from a table-level snapshot (§4.2) |
| pii_fields ≠ ∅ (gives `REPORT_EXPOSED_PII`) | any of email/phone/email_hash/name/user_id populated on a REDACT/ANONYMIZE-category record; `*_pii_scan` / `analytics_identity_scan` with `matched_value`; `direct_identifiers=1`; ledger `IDENTIFIABLE` |
| ANONYMIZED | analytics row with `user_id`, `customer_reference`, `email`, `phone` and `email_hash` all null; `direct_identifiers=0`; ledger `ANONYMIZED` |
| REDACTED | support row whose only identifier is `customer_reference=user_N` (requester_* null) or whose `message_text` is `[REDACTED]`; tombstone row with name/email/phone/email_hash null, `subject_reference` kept and `account_status=DELETED`; ledger `REDACTED` |
| FLOW_ACTIVE | `enabled` true/1, `last_delivery_status=delivered`, `scheduler_registered=true`, `connector_heartbeat`, `mode=continuous_sync`; ledger `DATA_FLOW ACTIVE` |
| FLOW_DISABLED | `enabled` false/0, `last_delivery_status=stopped`, `connector_config_loaded enabled=false`; ledger `DATA_FLOW DISABLED` |
| RESTORE_OPEN | `restore_allowed` true/1, `restore_candidate_evaluated eligible=true deletion_block=false`; ledger `BACKUP_ARCHIVE ACTIVE` |
| RESTORE_BLOCKED | `restore_allowed` false/0, `restore_authorization_completed decision=deny`; ledger `BACKUP_ARCHIVE BLOCKED` |

A stable `customer_reference=user_N` on a backup, flow, support or tombstone row is **not** exposed PII. In COMPLETE samples it sits on compliant rows: case_26 to case_28 and case_31 in evidence_92 and evidence_51.

### 1.5 Record kind → `deletion_rules.data_category`

| record kind (source) | category | rule → required state |
|---|---|---|
| account profile (`customer_profiles*`, `profile_lookup_*`, ledger `USER_PROFILE`) | USER_PROFILE | rule_01 → ABSENT |
| search doc (`customer_search_documents`, `search_documents_primary`, `index_query_*`, ledger `SEARCH_INDEX_ENTRY`) | SEARCH_INDEX_ENTRY | rule_03 → ABSENT |
| support conversation (`support_conversations`, `support_records`, `support_ticket_read_*`, `message_pii_scan`, `message_read`, ledger `SUPPORT_MESSAGE`) | SUPPORT_MESSAGE | rule_05 → REDACTED |
| support attachment (`ticket_attachments`, `attachment_pii_scan` with `file=*.pdf`, ledger `SUPPORT_ATTACHMENT`, PDF attachment) | SUPPORT_ATTACHMENT | rule_06 → ABSENT |
| analytics profile (`customer_analytics_*`, `analytics_profile_read*`, `analytics_identity_scan`, ledger `ANALYTICS_PROFILE`) | ANALYTICS_PROFILE | rule_07 → ANONYMIZED |
| analytics `contact_lookup_completed email_opt_in=true` (analytics_9914) | expected op is DELETE. Category is probably MARKETING_PROFILE (**open**) | rule_10 → ABSENT |
| legacy contact index (`support_replica contact_query_*`, support_002) | expected op is DELETE. Category is not stated (**open**) | → ABSENT |
| export (`customer_exports`, `customer_export_jobs`, `export_*_check/read`, ledger `USER_EXPORT`) | USER_EXPORT | rule_09 → ABSENT |
| security audit (`security_audit_*`, `audit_record_read_*`, ledger `SECURITY_AUDIT_LOG`) | SECURITY_AUDIT_LOG | rule_12 → PRESENT. Every `retention_until` is between 2031 and 2034 |
| legal hold (`retained_order_records`, `retained_order_loaded`, ledger `LEGAL_HOLD_RECORD`) | LEGAL_HOLD_RECORD | rule_13 → PRESENT. No sample uses it |
| backup (`backup_restore_entries`, `backup_catalog`, `restore_*`, ledger `BACKUP_ARCHIVE`) | BACKUP_ARCHIVE | rule_14 → retained + BLOCKED |
| tombstone (`deleted_customer_references`) | ACCOUNT_TOMBSTONE | rule_15 → REDACTED |
| connector (`connector_subscriptions`, `connector_configurations`, `connector_*`) | data flow (no rule row) | DISABLED |

No text evidence exists for CACHE_ENTRY, EMAIL_DELIVERY_LOG, PRODUCT_TELEMETRY or SECONDARY_IDENTIFIER. `cache_*` and `email_delivery_*` appear only in activity rows (REFRESH_CACHE, SEND_EMAIL). `marketing_*` appears only in a PNG and in one LINK row.

---

## 2. Per-family parser spec

Counts match the manifest: 24 sql, 28 json, 26 log, 1 txt, 11 png, 4 pdf.

### 2.1 SQL (24). Execute with sqlite3 in-memory, under the authorizer.

**A. `customer_data_inventory_*` (11 files, evidence_63 … evidence_93).** These are typed tables: `customer_profiles`, `customer_search_documents`, `customer_analytics_profiles`, `support_records`, `customer_exports`, `connector_subscriptions` (`enabled` 0/1), `backup_restore_entries` (`restore_allowed` 0/1) and `security_audit_records` (`retention_until`). `snapshot_scope(origin_system, captured_at)` lists the systems the snapshot covers. The footer comment `-- snapshot_completed_at=` repeats the time.
- Fact per row: `observed_at=updated_at`, system from the table (or the prefix), subject keys from the identifier columns. 0/1 integers map to FLOW_*/RESTORE_*.
- Edge cases: evidence_90 has one scope row and **zero data rows**. It proves nothing (§4.2). `enabled`/`restore_allowed` are sometimes stored as strings `'0'`/`'1'`. Emails can be upper-case.
- Example (evidence_93): `backup_restore_entries('backup_4978', NULL, '<email>', 'archive/…', '1', …)` gives RESTORE_OPEN. Case_09 cites it.

**B. Generic replica snapshots** (`customer_data_read_replica_*` ×5, `customer_data_regional_replicas_*` ×3, `customer_data_reporting_replica_*` ×2, `customer_data_failover_replica_*` ×1). Tables are `customer_data_primary` plus one or more replica tables (`customer_data_read_replica`, `customer_data_replica_ap_south`, `customer_data_replica_eu_west`, `customer_data_reporting_replica`, `customer_data_failover_replica`). Columns are `(resource_id, origin_system, collection_name, record_json, updated_at)`.
- Fact per row and table: parse `record_json`; `system=origin_system`; `observed_at=updated_at`. Keep `table` in the trail so drift is explainable.
- Drift (F-016): in every multi-table file, replica-only rows are account profiles: account_3150, account_9608, account_4348, account_8023, account_6345, account_994, account_5389, account_6539, account_8105, account_585, account_1035, account_3183 and account_005. No row differs field by field between primary and replica. A replica row that is PRESENT makes the resource PRESENT, even when the primary shows it ABSENT.
- The header comments `-- Captured at:` and `-- Database topology:` hold the capture time and the topology.

**C. `customer_accounts_failover_replica_20260902` (evidence_54).** Tables `customer_profiles_primary` and `customer_profiles_failover_replica` hold typed account rows with `user_id`. account_005 exists only in the replica (case_05 finding). The primary rows are decoys whose user ids are not in `user_identities.csv` and whose names look like real subjects.

**D. `customer_search_primary_20260910` (evidence_57).** Table `search_documents_primary(resource_id, display_name, email, source_resource_id, indexed_at)`. `source_resource_id` names the account the document was built from: search_001 comes from account_006 (case_06). Two decoy rows carry look-alike names.

### 2.2 JSON (28)

**A. `customer_data_snapshot_bundle_*` (12).** The shape is `{exported_at, source, snapshots:[{captured_at, data_store, collection, records:[…]}]}`. Collections:
`account_service/customer_profiles`, `search_service/customer_search_documents` (identifiers sit under `document.{display_name,email,customer_reference}`), `analytics_platform/customer_analytics_reports` (`user_id,email,phone,email_hash` plus metrics), `support_platform/support_conversations` (`subject_reference`, `message_text` free text that may contain an email or `[REDACTED]`), `support_platform/ticket_attachments` (`uploaded_by`, `file_name`), `export_service/customer_export_jobs`, `integration_service/connector_configurations` (`subject_selector`, `enabled`, `mode`), `backup_service/backup_catalog` (`subject_reference`, `restore_allowed`), `identity_service/deleted_customer_references` (tombstones), `security_service/security_audit_events` (`subject_reference`, `event_name`), `legal_service/retained_order_records`, and the ledger collections `*/operational_record_history` (§2.5).
- `observed_at` = snapshot `captured_at`. It can differ from the file's manifest time: evidence_02 holds snapshots stamped 2026-09-09 to 2026-09-17, but the manifest says 2026-09-17.
- An empty `records: []` for a collection is a table-level snapshot showing that no row exists. Case_31 cites evidence_51 for account_4857 ABSENT this way.

**B. `service_resource_export_*` (11).** The shape is `{exported_at, region, service_exports:{<system>:{<list>:[…]}}}`, with these lists: `account_service.profile_lookups` (`status_code`, `profile` null or an object), `analytics_platform.profiles`, `backup_service.restore_entries`, `export_service.exports`, `integration_service.connectors`, `search_service.index_queries` (`query`, `hits.total`, `hits.documents[]`), `security_service.audit_records` and `support_platform.tickets`. The system is the key under `service_exports`. `observed_at` is per record.
- Edge case: a 404 profile lookup carries **no identifier**. It proves ABSENT, but the link to the subject must come from elsewhere (§4.3).

**C. Ledger-shaped JSON:** `connector_configurations_20260812` (evidence_13), `customer_export_manifest_20260409` (evidence_36) and `security_audit_ledger_20261001` (evidence_50). Records are `{recorded_at, system, resource_id, record_type, result, subject_reference}`. See §2.5. The file names do not describe the contents: the "connector" file mostly holds account, search and security rows.

**D. `customer_analytics_report_20260907` (evidence_56).** `records[]` with `user_id,email,phone,email_hash`. analytics_901 is all-null, which makes it ANONYMIZED (case_04).

**E. `customer_export_jobs_20260914` (evidence_59).** `records[]` with `owner_email`, `download_available`, `expires_at`. export_001 is PRESENT (case_08).

### 2.3 Logs (26). Four groups.

**A. `resource_lookup_trace_*` (11, readback_collector).** These are `key=value` lines. Each `trace_id` (`rb-…`) has a `*_started` line carrying `lookup_key` (an email, user_id or `null`) and a `*_completed` line carrying `resource_id` and the state fields. Event pairs: `profile_lookup` (`rows`, `http_status`, identifiers), `index_query` (`result=hit`, `email`), `support_ticket_read` (`requester_*`, `customer_reference`), `analytics_profile_read` (identifiers, `audience_cohort`), `connector_config_read` (`enabled`, `last_delivery_status`, `customer_email`/`customer_reference`), `restore_policy_read` (`restore_allowed`, `archive_present`), `audit_record_read` (`subject_reference`, `event_code`, `retention_until`) and `export_metadata_read` (`available`, `owner_email`).
- **Join started and completed lines on `trace_id`.** The 404 completed line has no identifier; the link is `lookup_key` on the started line. An example is account_7566 in case_03.
- `lookup_key=null` together with all-null identifiers is an anonymized analytics row. It has no link (analytics_9406).

**B. Platform-service traces in six syntaxes (12 files).** The content is the same and only the envelope differs:

| family (files) | envelope | service / trace |
|---|---|---|
| `service_events_*` (2) | `ts level=… service=… trace_id=… event=… k=v` | kv |
| `structured_service_events_*` (2) | `ts {json}` | `service`, `trace_id` keys |
| `syslog_archive_*` (2) | `ts <pri>1 node app trace - - k="v"` | app = service, 4th token = trace |
| `application_trace_*` (2) | `ts [LEVEL] [service] [trace] event: k="v"` | brackets |
| `operations_stream_*` (2) | `ts \| LEVEL \| service \| trace \| event \| k="v"` | pipe fields |
| `cloud_runtime_export_*` (2) | `ts requestId=… level=… function=… message="k=\"v\" …"` | `function`, `requestId`. Unescape `\"` inside `message`; a naive split leaves a trailing `\` on the last value |

Events: `profile_lookup_started`/`_completed` (`rows`, `http_status`), `index_query_started`/`_completed` (`result=hit`), `message_scan_started` with `message_pii_scan` (`matched_value`), `attachment_scan_started` with `attachment_pii_scan` (`matched_value`, `file`), `audit_record_query_started` with `audit_record_read_completed` (`rows`, `integrity_check`), `analytics_profile_scan_started` with `analytics_profile_read` (`direct_identifiers=0`), `analytics_identity_scan` (`direct_identifiers=1`, `matched_value`), `connector_config_read_started` with `connector_heartbeat` (`enabled=true`) or `connector_config_loaded` (`enabled=false`), `restore_candidate_evaluated` (`eligible`, `deletion_block`), `restore_authorization_completed` (`decision=deny`), `export_download_check_completed` (`available`), `message_read` (`message_text=[REDACTED]`), `retained_order_loaded` and `contact_lookup_completed` (`email_opt_in`).
- The subject key sits on the `*_started` line (`lookup_key`, `match_key`, `subject_key`, `scan_key`, `subject_ref`, `owner_key`), or inline on the completed line as `correlation_key`. Join on trace id.
- **Pitfall:** `cache_lookup result=miss` and `dependency_retry` lines share the trace id. Never read the `result` of a cache line as the resource state. Take state fields only from the line that carries `resource_id`.
- Noise lines (`dns_cache`, `secret_agent`, `queue_consumer`, `webhook_delivery`, `feature_flags`, `circuit_breaker`, `lambda_extension`, `log_router`) carry no resource and should be dropped.

**C. Ledger logs:** `notification_delivery_20260315` (evidence_41) and `search_index_diagnostic_20260906` (evidence_08). Lines read `event=record_lookup seq=N system=… resource_id=… record_type=… result=… subject_reference=…` (§2.5). One file can hold two rows for the same resource with different times. evidence_08 has account_8473 FOUND at 08-31 and NOT_FOUND at 09-06, so the latest row at or before `audit_at` wins.

**D. `support_replica.log` (evidence_61).** Lines are `contact_query_started lookup_key=<email>` → `contact_query_completed resource_id=… rows=1`, followed by `deletion_marker_check marker_found=false`. Either line gives PRESENT (support_002, case_10). It also has unrelated `thumbnail_failed` and `consumer_lag` lines.

### 2.4 TXT (1): `customer_account_handover_20261001` (evidence_03)

Lines read `- <ts> | <system> | <resource_id> | <record_type> | <result> | <key>`, where key is an email, a user_id or `no direct identifier`. This is the ledger shape (§2.5). Cases 11, 13 and 14 cite it.

### 2.5 Ledger rows (TXT, three JSON files, two logs, snapshot `operational_record_history`)

Fields are `recorded_at`, `system`, `resource_id`, `record_type` (a rule category, or `DATA_FLOW`), `result`, and `subject_reference`/`lookup_value`. The observed (system, record_type, result) combinations are:
USER_PROFILE FOUND/NOT_FOUND · SEARCH_INDEX_ENTRY FOUND · SUPPORT_MESSAGE IDENTIFIABLE/REDACTED · SUPPORT_ATTACHMENT FOUND · ANALYTICS_PROFILE IDENTIFIABLE/ANONYMIZED · USER_EXPORT FOUND · SECURITY_AUDIT_LOG FOUND · LEGAL_HOLD_RECORD FOUND · BACKUP_ARCHIVE ACTIVE/BLOCKED · DATA_FLOW ACTIVE/DISABLED.
`record_type` is the category directly, and `result` maps onto §1.4.

### 2.6 PNG (11) and PDF (4): handled by Nemotron Parse in P2-02

| file_id | file | contents (from name, manifest, LINK row, or a quick look) |
|---|---|---|
| evidence_04 | account_admin_console_20260926.png | one customer screen: `user_11 · account_5762`, email, phone, support ref support_9538 (checked by eye) |
| evidence_09 | search_index_inspector_20260901.png | search entry, LINK row: search_428 / user_13 |
| evidence_14 | connector_management_console_20260807.png | connector, LINK row: data_flow_1121 / user_14 |
| evidence_19 | analytics_profile_view_20260713.png | analytics profile, LINK row: analytics_7438 / user_20 |
| evidence_23 | customer_export_console_20260618.png | export, LINK row: export_1260 / user_18 |
| evidence_28 | support_ticket_console_20260524.png | ticket, LINK row: support_1034 / user_22 |
| evidence_32 | backup_restore_console_20260429.png | backup, LINK row: backup_9287 / user_16 |
| evidence_37 | security_audit_explorer_20260905.png | events table for user_03: audit_record_001…006 (checked by eye) |
| evidence_42 | deleted_account_reference_20260310.png | tombstone, LINK row: tombstone_17 / user_17 |
| evidence_46 | object_storage_browser_20260213.png | attachment object, LINK row: object_19 / user_07 |
| evidence_60 | marketing_profile_console.png | marketing profile, LINK row: marketing_001 / user_09 |
| evidence_18 | account_history_report_20260718.pdf | text layer present (~700 chars), names user_18. LINK row: export_1842 (`NST-2026-0718-1842`) |
| evidence_27 | legal_retention_register_20260529.pdf | text layer names user_08, 12, 17, 21, 24, 29. None of the matching samples has a legal-hold step (**open**) |
| evidence_55 | security_retention_extract.pdf | text layer: audit_record_003, user_03 |
| evidence_58 | delivery_correction_attachment.pdf | text layer: support_001. **Cited** by case_07 (REPORT_REMAINING_RECORD) |

All four PDFs have a text layer (pypdf extracts 600–1000 chars each), so P2-02 can read text before falling back to OCR. Every LINK_RESOURCE_IDENTITY row is stamped exactly 7 minutes after the manifest time of its image or PDF (F-019).

---

## 3. `system_activity.csv` event types

The `details` text never contains a subject identifier, except on LINK_RESOURCE_IDENTITY rows. The subject link therefore always comes from evidence. Activity rows are **claims**. No sample cites an `activity_id`: all 75 cited steps cite a `file_id`.

| event_type (count) | source → target | details pattern | meaning for the auditor |
|---|---|---|---|
| DELETE_RECORD (890) | deletion_worker → account/search/support/export/analytics | "submitted primary profile X" / "received the final result for X" / "reported … completed" | Claim. `reported_result` does not predict the state: SUCCESS rows were still PRESENT (case_16 search_1007, case_24 account_5334 and search_5577, case_10 support_002), and FAILED rows were verified ABSENT (case_25, case_26, case_28 accounts) |
| ANONYMIZE_RECORD (204), REDACT_RECORD (173) | deletion_worker → analytics / support / identity | "Policy action completed for X" | Claim. In samples SUCCESS ↔ compliant and FAILED ↔ REPORT_EXPOSED_PII (22/22), but evidence must still prove it |
| CHECK_DATA_FLOW (89) | deletion_worker → integration | "…confirmed that data flow X remains enabled" | Claim of an active flow. 6/6 sample hits are flows reported ACTIVE |
| CHECK_RESTORE_ACCESS (28) | deletion_worker → backup | "…archive X can still be restored" | Claim of an open restore. 3/3 sample hits are RESTORE_RISK |
| DISABLE_DATA_FLOW (36), BLOCK_RESTORE (36) | deletion_worker → integration / backup | "Policy action completed" | Claim of remediation done. 6/6 sample hits verified DISABLED/BLOCKED |
| SYNC_RECORD (447) | account_service → account_replication_cluster / account_failover_replica / analytics; integration → search | "Replication worker … checkpoint", "Customer profile synchronization processed", "Active connector repopulated downstream resource X" | Recreation signal. The three replica syncs after a DELETE all line up with replica-drift REMAINING findings (case_05, case_16, case_24); the finding is on the account, not a flow |
| RESTORE_BACKUP (1) | backup → search | "Restore job repopulated downstream resource X" | Recreation signal. No sample resource |
| LINK_RESOURCE_IDENTITY (12) | data_catalog → various | "Data catalog linked X (alias) to <email> and user_N" | **Identity observation** that bridges an image/PDF to a subject. Valid only when its time is at or after `requested_at` (F-014) |
| CLASSIFY_REQUEST (10) | privacy_intake → privacy_case_management | "…classified request for account_N as non-deletion" | 10 rows. Exactly 10 request texts are non-deletion (§5). Probably a cross-check (**open**) |
| INDEX_RECORD (400), UPDATE_RECORD (672), REFRESH_CACHE (284), SEND_EMAIL (368), CREATE_EXPORT (155), RETAIN_RECORD (206) | various | "…processed X" | Background noise. None touches a sample resource |

---

## 4. Decision rules derived from the samples

### 4.1 Within-phase ordering rule (32/32)

Sort steps by `(phase index, index of operation in the spec table, system_id, resource_id)`, using this table order:
`REPORT_REMAINING_RECORD, REPORT_EXPOSED_PII, REPORT_ACTIVE_DATA_FLOW, REPORT_RESTORE_RISK, DISABLE_DATA_FLOW, BLOCK_RESTORE, DELETE_RECORD, REDACT_RECORD, ANONYMIZE_RECORD, VERIFY_RECORD_ABSENT, VERIFY_RECORD_PRESENT, VERIFY_RECORD_REDACTED, VERIFY_RECORD_ANONYMIZED, VERIFY_DATA_FLOW_DISABLED, VERIFY_RESTORE_BLOCKED`.
There is no dependency reordering (H2). Check: `check.py` sorted every sample's steps with this key and compared against the expected order and consecutive `step_no`. Result: 32/32 identical.

### 4.2 Evidence_id selection rule (75/75 cited steps)

1. REMEDIATION steps, and VERIFICATION steps of INCOMPLETE cases, use `""`. FINDING steps and COMPLETE verification steps cite a `file_id` (32/32 cases).
2. The candidates are files whose manifest `captured_at` is at or before `audit_at` (inclusive) and that hold an **explicit** row for that `resource_id` showing the state being cited. Cite the candidate with the latest `captured_at`. This reproduces 70 of 75 cited steps; one of them (case_07 support_001 → evidence_58) needs the PDF text layer. In every sample there was exactly one such candidate, so "latest" is the stated tie-break but the samples do not exercise it. Later-captured files that hold the resource are rejected: evidence_02 for cases 21 to 30, evidence_06 for case_09.
3. If no file shows the record explicitly and the state is ABSENT, cite the latest **table-level snapshot** of that system with `captured_at` at or before `audit_at` that contains at least one data row anywhere in the file. A table-level snapshot is a SQL table or a JSON snapshot collection, including an empty `records: []`. Lookup logs and ledgers prove only what they looked up, never an omission. This covers case_01, case_02 and case_04 (evidence_54; evidence_90 is later but has zero data rows, and evidence_08 is a lookup log) and case_31 (evidence_51), which is the remaining 4 of 75.
4. Never cite an `activity_id` or `audit_id` (0/75 in samples).

Check: `evid.py` classified every cited step as EXPLICIT-LATEST (70), OMISSION (4) or PDF (1), with no counter-example.

### 4.3 Resource set of a case (discovery)

- A resource belongs to the subject when a row carries one of the subject's identifiers (§1.2: case-insensitive email, user_id, hash, phone; trace-joined for logs) **and that row is observed at or after `requested_at`**. This held for 86/86 (case, resource, user) links in the samples. The three links observed before the request are decoys: case_07 object_19, case_17 tombstone_17 and case_17 account_6523, the last observed 2026-03-10 while the request came on 2026-08-19.
- Rows from files captured after `audit_at` still count for discovery. Eight expected resources are linked only that way: case_09 account_3960 and audit_record_4902 (evidence_06); case_23, case_24, case_29 and case_30 audit records, case_26 account_5684 and case_27 account_3866 (evidence_02). Their **state** still comes only from citable files.
- **Ceiling.** 28 of the 111 expected (case, resource) pairs have no identifier link in text evidence:
  - 14 accounts appear only in a deletion_worker activity row;
  - 10 account or analytics rows exist only with null identifiers, plus an activity row;
  - case_07 support_001 is linked only through the PDF;
  - 3 appear in no participant file at all: case_04 account_004, case_18 audit_record_6645, case_20 audit_record_5569.
- Every sample has exactly one account_service resource, which always appears in VERIFICATION.
- Leading hypothesis (**open**, for P1-10): deletion batches run once a day. Within a batch, subjects appear in the same relative order in every resource phase: accounts, then analytics, support, search, flows and backups. In the 2026-09-09 batch, accounts 5521, 5037, 9335 line up with case_18, case_20, case_13, and so do their support and search rows. Aligning orphan resources by batch position may recover part of the ceiling, but it has not been verified.

### 4.4 Finding → remediation → verification chains (22 INCOMPLETE cases; findings and remediations on the same resources 22/22)

| finding | remediation | verification | systems seen |
|---|---|---|---|
| REPORT_REMAINING_RECORD | DELETE_RECORD | VERIFY_RECORD_ABSENT | account, search, support, export, analytics (analytics_9914) |
| REPORT_EXPOSED_PII | REDACT_RECORD | VERIFY_RECORD_REDACTED | support, identity (tombstone) |
| REPORT_EXPOSED_PII | ANONYMIZE_RECORD | VERIFY_RECORD_ANONYMIZED | analytics |
| REPORT_ACTIVE_DATA_FLOW | DISABLE_DATA_FLOW | VERIFY_DATA_FLOW_DISABLED | integration |
| REPORT_RESTORE_RISK | BLOCK_RESTORE | VERIFY_RESTORE_BLOCKED | backup |
| (compliant) | none | VERIFY_RECORD_ABSENT / PRESENT | account (19), security (17) |

Status: INCOMPLETE when there is at least one finding, otherwise COMPLETE (32/32).

---

## 5. Request text (intent)

- 518 requests, 375 distinct texts, 27 distinct first sentences. English dominates; there are 14 Portuguese, 12 French and 12 Spanish texts, and the Portuguese and French opening sentences are each a single repeated template.
- 10 requests are non-deletion: case_533 to case_542, all `reported_status=NOT_STARTED`. Their patterns are: update the mobile number; stop promotional emails ("not asking for deletion"); download data in a portable format; login help ("Do not close the account"); fix a misspelled surname; **"remove me from marketing lists only"** (case_538, which defeats keyword rules); "what personal information you hold" (access); copy of invoices; change the email address; send a copy of my information ("please don't delete").
- Many non-deletion texts contain a deletion verb that is negated or scoped ("not asking for deletion", "Do not close", "without removing", "not a request to erase", "don't delete"). Negation and scope have to be handled.

## 6. Time: `audit_at` vs `captured_at` vs row time

- The manifest `captured_at` decides citability. In case_09, evidence_06 holds a backup_4978 row observed at 08:57 on 2026-09-16, three minutes before `audit_at`, but the file was captured on 2026-09-18. The sample cites evidence_93 instead.
- Inclusive bound: evidence_51 is captured at exactly `audit_at` (2026-09-15T12:00:00Z) and is cited by case_31 and case_32.
- Inside a file, the latest row at or before `audit_at` wins (evidence_08 account_8473).
- Late files can contradict the answer. In evidence_02, captured 2026-09-17, account_3866 is ACTIVE at 09-17, yet case_27 is COMPLETE with account_3866 ABSENT (evidence_92). Late evidence must never change state.

## 7. Traced cases (request → identity → evidence → steps)

| case | user (match) | resources → op [cited file and why] |
|---|---|---|
| case_01 | user_01 (current) | account_001 VERIFY_ABSENT [evidence_54: account table snapshot with no row] |
| case_03 | user_43 | account_7566 ABSENT, audit_record_2016 PRESENT, analytics_9406 ANONYMIZED [evidence_94: trace log, lookup_key join] |
| case_04 | user_04 | account_004 ABSENT [evidence_54, omission]; analytics_901 ANONYMIZED [evidence_56, all-null row] |
| case_05 | user_05 | account_005 REMAINING [evidence_54: failover-replica-only row, H6] |
| case_06 | user_06 | search_001 REMAINING [evidence_57]; account_006 verify only |
| case_07 | user_07 | support_001 REMAINING [evidence_58 PDF]; account_007 verify; object_19 LINK is pre-request, so excluded |
| case_08 | user_08 | export_001 REMAINING [evidence_59]; account_008 verify (H1) |
| case_09 | user_61 | backup_4978 RESTORE_RISK [evidence_93, restore_allowed=1]; account_3960 and audit_record_4902 verify (linked only by late evidence_06) |
| case_10 | user_10 (historical email) | support_002 REMAINING [evidence_61, support_replica] |
| case_11 | user_32 | search_052 REMAINING; analytics_2034 and support_864 EXPOSED_PII; data_flow_9522 ACTIVE [evidence_03 handover] |
| case_12 | user_12 (current) | analytics_9914 REMAINING → DELETE [evidence_01, linked by email_hash correlation_key] |
| case_13 | user_33 | search_1308 and support_4218 (SUPPORT_ATTACHMENT) REMAINING [evidence_03] |
| case_14 | user_37 | backup_3870 RESTORE_RISK [evidence_03] |
| case_15 | user_15 | data_flow_9846 ACTIVE [evidence_01, connector_heartbeat] |
| case_16 | user_53 | account_994 REMAINING [evidence_05, read-replica-only row, H6]; search_1007 REMAINING |
| case_17 | user_17 | backup_3245 RESTORE_RISK [evidence_01]; tombstone_17 and account_6523 are pre-request decoys |
| case_18 | user_50 | search_4013 REMAINING; analytics_037 and support_5569 EXPOSED_PII; data_flow_4890 ACTIVE [evidence_94]; audit_record_6645 is in no file |
| case_19 | user_19 | search_6083 REMAINING; support_9553 EXPOSED_PII [evidence_01, message_pii_scan] |
| case_20 | user_48 | search_4262 REMAINING; data_flow_1770 ACTIVE [evidence_94] |
| case_21 | user_21 | account_6440, audit_record_3737, analytics_5335 [evidence_92; evidence_02 is late] |
| case_22 | user_51 | search_8911 REMAINING; analytics_4440 EXPOSED_PII [evidence_05] |
| case_23 | user_23 | export_7364 and search_898 REMAINING [evidence_92] |
| case_24 | user_24 | account_5334 (200 with email) and search_5577 REMAINING [evidence_92] |
| case_26 | user_26 | six verifications incl. support REDACTED, flow DISABLED, backup BLOCKED [evidence_92] |
| case_29 | user_29 (historical email) | search, analytics, support, flow findings [evidence_92] |
| case_31 | user_541 | account_4857 ABSENT [evidence_51, empty collection], tombstone_440 REDACTED, audit_record_6909 PRESENT [evidence_51] |
| case_32 | user_542 | tombstone_9178 EXPOSED_PII [evidence_51: name/email/phone/hash still set] |

The remaining samples (02, 25, 27, 28, 30) follow the same patterns as their neighbours above. Three sample request emails are historical, not current: case_10, case_29 and case_30. None of the sample emails is upper-case.

## 8. Open questions

1. How do orphan resources (§4.3: 24 pairs linked only through activity rows or null-identifier rows) map to a subject? The batch-order alignment is untested. 3 expected pairs are absent from all participant data and cannot be recovered.
2. What category, and which rule id for the trail, applies to analytics_9914 (`contact_lookup email_opt_in`) and to support_002 (`legacy_contact_index`)? The expected op for both is DELETE.
3. Legal holds: no sample covers them. The register PDF names six users whose samples show no legal-hold step. Is the hold expired, or is the user a different one?
4. CLASSIFY_REQUEST rows: do they map one-to-one to the 10 non-deletion requests? That would give an independent check for intent.
5. When several citable explicit files show the same state, "latest captured" is the stated tie-break, but no sample exercises it.
