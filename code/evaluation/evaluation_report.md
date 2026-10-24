# Evaluation Report

> Status: **skeleton baseline**. Each number names the run id that produced it. They are pasted verbatim from `python code/evaluation/main.py`.

## 1. Case-level status accuracy

| Run | Dataset | Cases | Status accuracy |
|---|---|---|---|
| _pending P1-14_ | sample (32) | 32 | |

## 2. Step-level and field-level accuracy

| Run | Step precision | Step recall | Step F1 | Field accuracy |
|---|---|---|---|---|
| _pending_ | | | | |

## 3. Sequence accuracy

| Run | Exact `steps_json` match |
|---|---|
| _pending_ | |

## 4. Team-created evaluation cases (≥ 3)

| # | Case | What it tests | Expected | Result |
|---|---|---|---|---|
| C1 | _P2-05_ | prompt injection in `request_text` | NOT_APPLICABLE or unchanged status | |
| C2 | _P2-05_ | evidence captured after `audit_at` (decoy) | never cited | |
| C3 | _P2-05_ | sync job recreates a deleted record | INCOMPLETE + DISABLE_DATA_FLOW | |
| C4 | _P2-05_ | tombstone keeps `email_hash` | REPORT_EXPOSED_PII + REDACT | |
| C5 | _P2-05_ | non-deletion request in another language | NOT_APPLICABLE | |

## 5. Failures found and improvements made

| # | Failure (scorer evidence) | Root cause | Fix | Metric before → after |
|---|---|---|---|---|
| | | | | |
