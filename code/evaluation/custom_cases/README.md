# Custom evaluation cases

The six team-created cases live in `../custom_cases.py` (one builder function each, with its hand-written derivation in the
`derivation` field). All inputs are synthetic and built in memory: `example.com` emails, `user_90x` ids, `*_9xxx` resource ids,
no dataset identifiers. Only `dataset/deletion_rules.csv` (policy text, no personal data) is read.

Each case runs the real `pipeline.audit_case` (intent, identity, link, evaluate, plan), validates the row with
`contract.validate_row`, and compares `(status, steps)` with the expected result.

    python code/evaluation/custom_cases.py          # PASS/FAIL table, exit 1 on failure
    pytest code/tests/test_custom_cases.py -q

To add a case: write a builder returning `id, tests, email, identity, facts, [activity], text, expect, derivation`, derive `expect`
by hand from `deletion_rules.csv` and the problem statement (never from the pipeline output), and append it to `CASES`.
