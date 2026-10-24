# Dev gate log

Append-only. Written by `scripts/gate.py`.

| Time (UTC) | Gate | Verdict | Summary | Actor | Commit |
|---|---|---|---|---|---|
| 2026-10-24T18:23:31Z | contract | PASS | output.csv valid (G7) | coordinator | 0eddbbd |
| 2026-10-24T18:23:31Z | eval | PASS | status=0.000 step_f1=0.000 field=0.000 seq=0.000 (32 cases) | coordinator | 0eddbbd |
| 2026-10-24T18:23:31Z | security | FAIL | 1 problems; first: golden-leak code/main.py | coordinator | 0eddbbd |
| 2026-10-24T18:23:32Z | package | PASS | code.zip with 30 files, secret scan clean | coordinator | 0eddbbd |
| 2026-10-24T18:23:43Z | security | PASS | 93 files clean (secrets, unsafe APIs, golden leak, PII, .env) | coordinator | 0eddbbd |
| 2026-10-24T18:48:09Z | contract | PASS | output.csv valid (G7) | coordinator | f557131 |
| 2026-10-24T18:48:09Z | eval | PASS | status=0.000 step_f1=0.000 field=0.000 seq=0.000 (32 cases) | coordinator | f557131 |
| 2026-10-24T18:48:09Z | security | FAIL | 1 problems; first: secret code/tests/test_llm.py: nvapi-[A-Za-z0-9_\-]{20, | coordinator | f557131 |
| 2026-10-24T18:48:09Z | package | FAIL | missing=[] secrets=['tests/test_llm.py: nvapi-[A-Za-z0-9_\\-]{20,'] | coordinator | f557131 |
| 2026-10-24T18:48:24Z | security | PASS | 96 files clean (secrets, unsafe APIs, golden leak, PII, .env) | coordinator | f557131 |
| 2026-10-24T18:48:24Z | package | PASS | code.zip with 32 files, secret scan clean | coordinator | f557131 |
| 2026-10-24T18:48:50Z | security | PASS | 96 files clean (secrets, unsafe APIs, golden leak, PII, .env) | coordinator | f557131 |
