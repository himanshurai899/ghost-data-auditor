# Evaluation Report

> Status: **P1 (MVP) baseline, deterministic pipeline, offline, no LLM calls at run time.** Numbers come from `python code/evaluation/main.py` on the 32 public samples (`dataset/sample_output.csv`). Run id of the final full run: `20261025T114242Z-413437`. The pipeline never reads the sample answers.

## 1. Case-level status accuracy

| Run | Dataset | Cases | Status accuracy |
|---|---|---|---|
| P1 baseline (temporal default) | sample | 32 | **0.969** |
| P1 baseline (`--strict-temporal`) | sample | 32 | 0.969 |

## 2. Step-level and field-level accuracy

| Run | Step precision | Step recall | Step F1 | Field accuracy |
|---|---|---|---|---|
| P1 baseline (default) | 0.994 | 0.896 | **0.943** | **0.830** |
| P1 baseline (`--strict-temporal`) | 0.994 | 0.870 | 0.928 | 0.776 |

Both readings of the late-evidence rule are reported (D-017). Default: files captured after `audit_at` may reveal which resources belong to the person, but state and citations use only files captured on or before `audit_at`. Strict: late files are ignored entirely. The default matches the labeled samples better, because several expected resources are linked only through late files (F-015).

## 3. Sequence accuracy

| Run | Exact `steps_json` match |
|---|---|
| P1 baseline (default) | **0.531** (17 of 32 cases) |
| P1 baseline (`--strict-temporal`) | 0.500 (16 of 32 cases) |

## 4. Full-dataset run (518 requests)

| | Count |
|---|---|
| Rows / contract (G6) failures / warnings | 518 / 0 / 0 |
| COMPLETE / INCOMPLETE / NOT_APPLICABLE | 151 / 357 / 10 |
| Workflow said COMPLETE but audit says INCOMPLETE | 165 of 254 |

The 10 NOT_APPLICABLE rows are the 10 non-deletion requests found by the intent rules (access, export, correction, marketing opt-out, login help).

## 5. Team-created evaluation cases (>= 3)

Pending (P2-05): prompt injection in `request_text`, evidence captured after `audit_at` (decoy), a sync job recreating a deleted record, a tombstone that kept `email_hash`, a non-deletion request in another language.

## 6. Failures found and improvements made

| # | Failure (scorer evidence) | Root cause | Fix | Metric before to after |
|---|---|---|---|---|
| 1 | All 32 samples wrong, every case a placeholder | planner, state and policy stages were stubs | state reconstruction, policy engine, planner | status 0.000 to 0.875, step F1 0.000 to 0.849 |
| 2 | Cases 10, 12, 13 emitted REDACT/ANONYMIZE where gold is DELETE | category taken from the first fact, and activity claims carry only an id-prefix guess | prefer categories from file-observed facts | step precision 0.944 to 1.000, F1 0.859 to 0.910 |
| 3 | Account, audit record and anonymized analytics rows missing (cases 01-09, 18-27); cases 01, 02, 04 degraded to NOT_APPLICABLE | those resources carry no identifier tying them to the person | orphan linking from the daily deletion-batch structure (id alignment, account batch, analytics grid) | status 0.906 to 0.969, sequence 0.219 to 0.438 |
| 4 | PDF/PNG-only resources absent (case_07) | images and PDFs were not parsed | Nemotron Parse + PDF text layer, cached with hashed emails | status 0.875 to 0.906 |

Remaining known ceiling: three expected resources appear in no participant file (case_04 account_004, case_18 audit_record_6645, case_20 audit_record_5569); audit records have no activity row, so none can be linked by batch structure; accounts in ties of three or more candidates are skipped on purpose.
