# Ghost Data Deletion Auditor

This tool audits whether each deletion request in `dataset/deletion_requests.csv` has actually been carried out, and writes `output.csv` (`case_id,deletion_status,steps_json`).

The core is deterministic: identity resolution, temporal filtering, state reconstruction, policy rules and step ordering are plain code. LLMs on NVIDIA build handle only what code can't: multilingual intent, screenshot and PDF reading, and flagged ambiguity. Typed gates (G1–G7) check every stage, and every run leaves a readable audit trail.

Design: `docs/architecture.md` (in the source repo).

## Setup

Requires Python 3.11+. The offline pipeline uses only the standard library.

```text
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r code/requirements.txt
copy .env.example .env            # optional: add NVIDIA_API_KEY for --online
```

## Layout of the submitted archive

`code.zip` contains the contents of this `code/` folder (`main.py`, `ghost/`, `prompts/`, `config/`, `data/`, `evaluation/`, `tests/`, `README.md`, requirements). Unpack it as `code/` inside a checkout that also has the organizer's `dataset/` folder; paths are resolved relative to that repository root, and `output.csv` is written there.

## Run (from the repository root)

```text
python code/main.py                              # all cases -> ./output.csv (offline, cache only)
python code/main.py --online                     # allow NVIDIA LLM calls for cache misses
python code/main.py --cases case_33 case_34      # partial run
python code/main.py --requests dataset/sample_deletion_requests.csv --out runs/sample_pred.csv
python code/evaluation/main.py --pred runs/sample_pred.csv   # score vs sample_output.csv
```

Each run writes `runs/<run_id>/manifest.json`, `trail.jsonl` and `report.md` (a human-readable audit trail with PII masked).

## Tests and gates

```text
pip install -r code/requirements-dev.txt
python -m pytest code/tests -q
python scripts/gate.py all          # contract · eval · security · package -> audit/gate_log.md
```

## Configuration (environment only; see `.env.example`)

| Variable | Purpose |
|---|---|
| `NVIDIA_API_KEY` | NVIDIA build key (never commit it) |
| `LLM_BASE_URL` | OpenAI-compatible endpoint (default NVIDIA build) |
| `LLM_MODEL_FAST` / `LLM_MODEL_REASON` / `LLM_MODEL_VISION` / `EMBED_MODEL` / `GUARD_MODEL` | model per role |
| `LLM_RPM`, `LLM_MAX_CALLS` | client-side rate limit and per-run call budget |

## Layout

`main.py` CLI · `ghost/` pipeline (contract, safety, evidence, identity, intent, reasoning, planner, llm, audit, pipeline, api) · `prompts/` · `config/` · `evaluation/` (scorer + reports) · `tests/`

## Operator console API

```
pip install -r code/requirements.txt
cd code && python -m ghost.api        # binds 127.0.0.1:8000 only; contract in docs/console_api.md
```

`GET /api/token` returns the per-start token that every `POST` must send as `X-Console-Token`.
