---
name: eval-runner
description: Runs the pipeline on the 32 public sample cases and custom cases, scores against sample_output.csv (status, step-level, field-level and sequence accuracy), compares with the last baseline, and updates code/evaluation/evaluation_report.md. Use after any change to code/ghost/, before merging, and at every phase exit (dev gate DG4).
---

# Eval Runner

## Commands

```text
python code/main.py --requests dataset/sample_deletion_requests.csv --out runs/sample_pred.csv
python code/evaluation/main.py --pred runs/sample_pred.csv --gold dataset/sample_output.csv
python scripts/gate.py eval          # does both + regression check + gate_log row
```

## Metrics

| Metric | Definition |
|---|---|
| Status accuracy | share of cases where `deletion_status` matches |
| Step-level F1 | multiset match of `(phase, system_id, resource_id, operation, state, evidence_id)` per case, micro-averaged |
| Field-level accuracy | per-position, per-field match over aligned steps |
| Sequence accuracy | share of cases whose full `steps_json` array is exactly equal (ignoring object-key order) |

## Rules

- **No regression.** DG4 fails if any metric drops versus the last PASS row in `audit/gate_log.md`, unless `decisions.md` records why.
- **No leakage.** Sample answers are for measurement only. Never copy them into code, prompts or few-shot examples that the pipeline uses at runtime. The one permitted use is the embedding neighbour index of sample *request texts with intent labels* (P2-03), which is recorded as an explicit decision in `decisions.md`.
- **Report honestly.** `evaluation_report.md` numbers come from the scorer output, pasted verbatim, and each set of numbers names the run id.
- **Custom cases** live in `code/evaluation/custom_cases/` as `requests.csv` + `expected.csv` + `README.md` explaining how each expectation was derived.
