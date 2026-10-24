# Pitfalls

Format: **symptom** → cause → fix.

- **Python's `sorted()` on case ids puts `case_100` before `case_33`** → lexicographic sort → use numeric sort (F-002). `contract.case_sort_key` does this.
- **Windows console prints `·`/`—` as `�`** → cp1252 console, not file corruption → files are UTF-8; set `PYTHONIOENCODING=utf-8` when piping.
- **A shallow clone can't be pushed to a new remote** → "shallow update not allowed" → `git fetch --unshallow upstream` before the first push.
- **Git warns "LF will be replaced by CRLF"** → global `core.autocrlf=true` on Windows; AGENTS.md wants `\n` in log.txt → `.gitattributes` with `* text=auto eol=lf`.
- **The security gate flags `sample_output` in any pipeline file, even inside a docstring** → this is intended (T8) → name prediction files `runs/sample_pred.csv`; don't allowlist.
