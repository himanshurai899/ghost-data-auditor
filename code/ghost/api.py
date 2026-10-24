"""Operator console API (FastAPI). Drives pipeline.run(); never forks its logic.

TODO(P3-01): 127.0.0.1 bind, CORS + Host allowlist, X-Console-Token on mutating routes, regex-validated
run/case ids, Pydantic extra="forbid", single-run lock, CSP header (threats T13-T17).
Routes: POST /api/runs · GET /api/runs/{id}/events (SSE) · GET /api/cases/{id} · POST /api/ask
"""
