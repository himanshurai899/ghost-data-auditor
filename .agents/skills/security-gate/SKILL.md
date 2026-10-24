---
name: security-gate
description: Runs the security gate (DG5) for the Ghost Data project — secret scan, golden-label leakage scan, unsafe-API scan (eval/exec/pickle/shell=True/dangerouslySetInnerHTML), PII-in-log scan, .env tracking check — and reviews changes against the threat model T1–T17 in docs/architecture.md §7. Use before every commit or merge, before packaging, and whenever code touches parsing, the LLM client, the API, or the UI.
---

# Security Gate

## Command

```text
python scripts/gate.py security
```

## What it checks (automated)

| Check | Threat |
|---|---|
| High-entropy or known-format secrets (`nvapi-`, `sk-`, `ghp_`, AWS keys, private keys) in tracked files and `log.txt` | T1 |
| `.env` tracked by git | T1 |
| `sample_output.csv` referenced outside `code/evaluation/` | T8 |
| `eval(`, `exec(`, `pickle.load`, `shell=True`, `os.system(` in `code/` and `scripts/` | T4, T14 |
| `dangerouslySetInnerHTML` in `web/src` | T17 |
| Dataset email addresses present in `log.txt` or committed docs | T9 |

## Manual review checklist (for changes the scanner cannot judge)

- [ ] New untrusted input? It needs validation at the boundary (regex or schema) and a size cap.
- [ ] New file read? The path goes through `safety.safe_evidence_path`.
- [ ] New SQL execution? It runs through `safety.open_sandboxed_sqlite` (authorizer on).
- [ ] New LLM prompt? Untrusted text is wrapped in tags and marked as data, output is schema-validated, and the model can't introduce ids that aren't in the candidate set.
- [ ] New API route? It has a regex-validated id, `extra="forbid"`, and a token check on mutating routes, with no file path in its params.
- [ ] New human-readable output? Identifiers go through `safety.mask()`.
- [ ] New dependency? It is pinned, justified in `decisions.md`, and not replaceable by the stdlib.

## Policy

- A FAIL blocks merge. The security-guardian may add an allowlist entry in `scripts/gate.py` only with a `decisions.md` entry. It never approves its own exception: the coordinator countersigns.
