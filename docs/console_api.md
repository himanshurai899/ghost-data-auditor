# Operator console API contract (P3)

Single source of truth for `code/ghost/api.py` (FastAPI) and `web/` (React). Everything is JSON unless noted. The API binds `127.0.0.1:8000`; the UI dev server proxies `/api` to it (`web/vite.config.ts`).

**Rules (threats T13-T17, docs/architecture.md §7):**

- Mutating routes (`POST`) require header `X-Console-Token`. The token is random per server start, returned by `GET /api/token` (same-origin only; the response carries no CORS headers).
- Allowed `Host`: `127.0.0.1:8000`, `localhost:8000`, `127.0.0.1:5173`, `localhost:5173`. CORS allow-list = `http://127.0.0.1:5173`, `http://localhost:5173`. Reject anything else with 403.
- Ids are regex-validated: `run_id` `^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}$`, `case_id` `^case_[0-9]{1,4}$`. No path parameters accept free text. Request bodies are Pydantic models with `extra="forbid"` and max lengths.
- One run at a time: `POST /api/runs` returns 409 while another run is active.
- Every identifier shown to the browser is masked with `ghost.safety.mask` / `mask_text`. The API never returns file paths, keys or raw request text.
- Responses carry `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`.
- The NVIDIA key is read server-side only. The UI never calls NVIDIA.

## Endpoints

| Method and path | Request | Response |
|---|---|---|
| `GET /api/health` | | `{"ok": true, "version": "..."}` |
| `GET /api/token` | | `{"token": "..."}` |
| `GET /api/runs` | | `[{"run_id", "started", "cases", "counts": {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}, "strict_temporal", "output_sha256"}]` newest first (reads `runs/*/manifest.json`) |
| `POST /api/runs` | `{"dataset": "full" or "sample", "cases": ["case_33"]?, "strict_temporal": false}` | `{"run_id"}`; the run executes in a background thread via `pipeline.run(...)`, offline |
| `GET /api/runs/{run_id}` | | manifest fields plus `counts` and `claim_matrix`: `{"reported": {"COMPLETE": {"COMPLETE": n, "INCOMPLETE": n, "NOT_APPLICABLE": n}, "PARTIALLY_COMPLETE": {...}, "NOT_STARTED": {...}}}` and `"running": bool` |
| `GET /api/runs/{run_id}/events` | `Accept: text/event-stream`, optional `?from=<index>` | SSE; each message `data:` is one `trail.jsonl` event (`ts, run_id, case_id, stage, gate, verdict, summary, evidence_ids, detail`). Sends an `event: done` message when the run has finished |
| `GET /api/runs/{run_id}/cases` | optional `?status=`, `?reported=`, `?q=` (case id prefix) | `[{"case_id", "reported", "status", "steps": n, "warns": n, "fails": n}]` numeric order |
| `GET /api/runs/{run_id}/cases/{case_id}` | | `{"case_id", "reported", "reported_at", "requested_at", "audit_at", "status", "intent": {"label", "source", "flags"}, "identity": {"user_id", "email_count", "phone_count"}, "steps": [step...], "trail": [event...]}`; step = the contract step object |
| `GET /api/runs/{run_id}/cases/{case_id}/timeline` | | `{"requested_at", "reported_at", "audit_at", "items": [{"observed_at", "captured_at", "system_id", "resource_id", "observation", "evidence_id", "is_claim", "citable": bool}]}` sorted by `observed_at`, restricted to the case's discovered resources; masked |
| `GET /api/runs/{run_id}/cases/{case_id}/identity` | | `{"nodes": [{"id", "kind": "user"/"email"/"phone"/"hash"/"resource", "label", "current": bool}], "edges": [{"from", "to", "label"}]}` (labels masked; resources are the case's discovered resources, edges from the identifier that linked them) |
| `GET /api/runs/{run_id}/usage` | | the contents of `runs/<id>/usage.jsonl` summarised: `{"calls", "cached", "tokens", "by_model": [...], "output_sha256", "deterministic": bool or null}` |
| `POST /api/redteam` | `{"text": "..."}` max 2000 chars | `{"label", "confidence", "source", "flags", "status_would_be": "unchanged"/"changed"}`: runs `intent.classify` on the text (rules only) |
| `POST /api/ask` | `{"run_id", "question"}` max 500 chars | `{"answer", "citations": [{"case_id"?, "evidence_id"?, "summary"}], "refused": bool, "reason"?}` grounded in the run trail |

## UI screens (web/src)

| Screen | Endpoints | Issue |
|---|---|---|
| Live gate board (stages and gates per case, red cases clickable) | `/events`, `/cases` | #34 |
| Claim vs truth (matrix, ghost counter) | `/runs/{id}` | #35 |
| Case explorer and resurrection timeline | `/cases/{id}`, `/timeline` | #36 |
| Identity graph | `/identity` | #37 |
| Ask the auditor | `POST /ask` | #38 |
| Red-team panel | `POST /redteam` | #39 |
| Cost and determinism badge | `/usage` | #40 |
