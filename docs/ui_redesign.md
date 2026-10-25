# Console redesign (UI/UX) — brief and API addendum

Design source of truth: `design-system/ghost-audit-console/MASTER.md` (generated with the ui-ux-pro-max skill: data-dense dashboard style, horizontal-journey landing, blue data + amber highlight). Adaptations for this project: **no external fonts or CDNs** (the browser may only call the local API; use system stacks: `ui-sans-serif, system-ui` for text, `ui-monospace, "SFMono-Regular", Consolas` for ids/code), SVG icons only (hand-written inline set, no emoji icons), no chart/graph libraries (inline SVG).

## Information architecture

| Route (hash) | Page | Purpose |
|---|---|---|
| `#/` | **Landing** | What the system is and how it works: the horizontal pipeline (S0..S8) with gates G1-G7 as hoverable/focusable/tappable cards; live numbers from the latest run; "Run audit" and "Open dashboard" actions |
| `#/dashboard` | **Dashboard** | Latest run at a glance: KPI cards, status mix, claim-vs-truth ghost meter, findings by system, gate health, run history |
| `#/cases` | **Cases** | Filterable table (status, reported, search) with ranking chips; selecting a case opens the case page |
| `#/cases/<case_id>` | **Case** | Header, evidence chain (ranked + colour coded), resurrection timeline, identity graph, steps by phase |
| `#/live` | **Live run** | Gate board over SSE (existing screen, restyled) |
| `#/ask` | **Ask the auditor** | Existing chat, restyled |
| `#/redteam` | **Red team** | Existing panel, restyled |
| `#/cost` | **Cost and metrics** | Calls, tokens, per-model rows, cache hits, billed vs estimated cost, one-time cache-build usage, run-time/determinism facts |
| `#/settings` | **Settings** | NVIDIA configurator: keys (stored encrypted, shown only as a reference), model per role, test connection |

Global: left rail on desktop (collapses to a bottom tab bar under 768px), top bar with run selector, API health pill, theme toggle (light/dark/system, persisted in try/catch localStorage), and a skip link.

## Evidence ranking and colour code (used everywhere an evidence id is shown)

Each cited evidence id gets a **tier** (computed by the API, shown as a chip with a letter + label so colour is never the only signal):

| Tier | Label | Meaning | Colour token |
|---|---|---|---|
| A | Direct | citable file row (captured at or before `audit_at`) showing the resource in the cited state | `--ev-a` green |
| B | Inferred | absence proven by omission from a citable table-level snapshot of the system | `--ev-b` blue |
| C | Claim | workflow or activity claim only; never sufficient alone, never cited in output | `--ev-c` amber |
| D | Late | captured after `audit_at`: used for discovery only, never for state or citation | `--ev-d` red-grey, hatched |
| X | None | future step (remediation / post-remediation verification), no evidence by design | `--ev-x` neutral |

`score` (0-100) = tier base (A 100, B 75, C 40, D 10, X 0) minus a recency penalty (days between evidence capture and `audit_at`, capped at 20). Ranking = descending score; ties by evidence id.

## API addendum (implemented by `code/ghost/settings_api.py`, `metrics_api.py`; all follow the rules of docs/console_api.md: token on POST/PUT/DELETE, masked output, extra=forbid, validated ids, no paths, no stack traces)

### Settings (NVIDIA configurator, key vault)

Keys are NEVER returned by any endpoint. The vault stores each secret encrypted at rest (Windows: DPAPI; elsewhere: Fernet with a 0600 master key file; if neither is available, saving is refused with 501 and the UI explains `.env` use). The UI sees only a **reference** (`ref`, a UUID4).

| Method and path | Request | Response |
|---|---|---|
| `GET /api/settings` | | `{"keys": [{"ref", "label", "roles": ["embed", ...], "preview": "nvapi-…ab12", "created", "last_test": {"ok", "at", "latency_ms", "model"}?, "storage": "dpapi"/"fernet"}], "active": {"<role>": "<ref>"}, "models": {"<role>": "<model id>"}, "base_url", "retrieval_url", "env_keys": {"<ROLE>": true/false}, "vault_available": bool}` (`env_keys` says whether an environment/.env key exists for each role, never the value; `preview` = `nvapi-` + last 4 chars only) |
| `POST /api/settings/keys` | `{"label": str(1..40), "value": str(20..200), "roles": ["default"/"embed"/"embed_large"/"rerank"/"parse"/"chat", ...]}` | `{"ref"}`; value must match `^nvapi-[A-Za-z0-9_-]{20,}$` |
| `DELETE /api/settings/keys/{ref}` | | `{"ok": true}` (securely overwrites the stored ciphertext) |
| `PUT /api/settings/active` | `{"role": str, "ref": uuid or null}` | `{"ok": true}` (which stored key a role uses; null = fall back to env) |
| `PUT /api/settings/models` | `{"role": "fast"/"reason"/"vision"/"guard"/"embed"/"embed_large"/"rerank"/"parse", "model": str(3..80) matching ^[A-Za-z0-9._/-]+$}` | `{"ok": true}` |
| `GET /api/settings/catalog` | | `{"models": [{"id", "owned_by"}...]}` from the public NVIDIA `/v1/models` list, cached 10 min; suggestions only |
| `POST /api/settings/test` | `{"ref": uuid or null, "role": str}` (`ref` null tests the env/.env key) | `{"ok": bool, "status": int or null, "latency_ms": int, "model": str, "message": str}`; makes ONE tiny real call per role (embed: 1-word embedding; chat roles: 1-token completion; rerank: 1 passage; parse: skipped with `ok: true, "message": "not testable without an image; key accepted by the gateway"` after an authenticated `GET /v1/models` check); messages never contain the key |

`llm.api_key(role)` resolution order becomes: environment variable (`NVIDIA_API_KEY_<ROLE>`, then `NVIDIA_API_KEY`) > active vault ref for the role > active vault ref for `default`. Per-process cache only. `llm.model(role)` honours `PUT /api/settings/models` overrides stored in `.ghost/settings.json` (gitignored) below env vars.

### Metrics, dashboard, evidence chain

| Method and path | Response |
|---|---|
| `GET /api/dashboard?run_id=` (default latest) | `{"run_id", "cases", "counts": {...}, "claim_matrix": {...}, "ghosts": {"count", "of", "pct"}, "findings_by_system": [{"system_id", "records", "pii", "flows", "restores"}], "gates": [{"gate", "pass", "warn", "fail"}], "runs": [{"run_id", "started", "cases", "counts", "output_sha256", "strict_temporal", "duration_s"}], "evidence_mix": {"A": n, "B": n, "C": n, "D": n}}` |
| `GET /api/metrics/cost?run_id=` (default latest) | `{"run": {"run_id", "requests", "calls", "cached", "live", "tokens_in", "tokens_out", "avg_tokens_per_request", "est_cost_usd" or null, "billed_usd": 0, "by_model": [{"provider", "model", "role", "calls", "cached", "tokens_in", "tokens_out", "est_cost_usd" or null}], "calls_over_time": [{"t", "calls"}]}, "cache_build": {"calls", "by_model": [...]}, "all_runs": [{"run_id", "calls", "tokens", "duration_s"}], "pricing": {"source": str or null, "rates_known": bool}, "notes": [str]}` (sourced from `runs/<id>/usage.jsonl`, the manifest, `code/data/usage_cache_build.jsonl`, `code/config/pricing.json`; no invented numbers: unknown token counts are `null`) |
| `GET /api/runs/{run_id}/cases/{case_id}/evidence` | `{"chain": [{"step_no", "phase", "operation", "system_id", "resource_id", "state", "evidence_id", "tier", "tier_label", "score", "captured_at", "observed_at", "citable", "why": str}], "ranking": [{"evidence_id", "tier", "score", "used_by_steps": [step_no...]}], "summary": {"A": n, "B": n, "C": n, "D": n, "X": n}}` |

## Shared frontend rules

- Tokens, spacing, radii, elevations, status and evidence colours as CSS variables in `web/src/styles/tokens.css` (light and dark, `prefers-color-scheme` plus a `data-theme` override). Text contrast >= 4.5:1 in both modes; borders visible in both.
- 44px minimum touch targets; visible focus ring (3px); `prefers-reduced-motion` respected; transitions 150-250ms on color/opacity/transform only.
- Tooltips: open on hover and on keyboard focus, toggle on click/tap, close on Escape and outside click, `role="tooltip"` + `aria-describedby`, never the only way to reach information (the same text is in the page or a legend table).
- Every chart has a table or text alternative; never colour alone (letters, icons, patterns).
- Loading skeletons for anything > 300 ms; empty and error states with a next action; reserve space to avoid layout jumps.
