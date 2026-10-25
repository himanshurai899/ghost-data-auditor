"""Operator console API (FastAPI), contract in docs/console_api.md. Drives pipeline.run(); never forks its logic.

Run:  python -m ghost.api   (from code/; binds 127.0.0.1:8000 only)

Controls (threats T13-T17): Host + CORS allow-lists, X-Console-Token on every POST/PUT/DELETE (constant-time compare),
regex-validated ids, Pydantic extra="forbid" with max lengths, single-run lock, CSP + nosniff, every string
masked on the way out, generic error bodies (no paths, no stack traces), SSE tails only the validated run's
trail file with a hard lifetime cap.

`POST /api/ask` lives in ghost/ask.py, which exposes `register(app, deps)`. `deps` is a SimpleNamespace with:
    runs_dir      Path                     directory holding runs/<run_id>/
    validate_run_id(run_id) -> str         raises HTTPException(422) unless the id matches the run-id regex
    load_trail(run_id) -> list[dict]       the run's masked trail events (404 if the run is unknown)
    mask_text(text) -> str                 ghost.safety.mask_text
The token check, Host/CORS checks, CSP headers and body-size cap are middleware, so they cover ask's POST too.
"""
import asyncio
import csv
import hashlib
import json
import re
import secrets
import threading
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from . import evidence, identity, intent, orphan, pipeline, reasoning
from .audit import _scrub as scrub, new_run_id
from .contract import DATASET, REPO, REPORTED_STATUSES, STATUSES, case_sort_key, load_evidence_index, read_csv, ts
from .safety import mask, mask_text

VERSION = "1.0"
RUNS_DIR = REPO / "runs"
RUN_ID = r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}$"
CASE_ID = r"^case_[0-9]{1,4}$"
_RUN_RX, _CASE_RX = re.compile(RUN_ID), re.compile(CASE_ID)
HOSTS = {"127.0.0.1:8000", "localhost:8000", "127.0.0.1:5173", "localhost:5173"}
ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}
CSP = "default-src 'self'"
MAX_BODY = 8192
SSE_MAX_SECONDS = 900
REQUEST_FILES = {"full": "deletion_requests.csv", "sample": "sample_deletion_requests.csv"}

TOKEN = secrets.token_urlsafe(32)  # random per server start
_lock = threading.Lock()           # single run at a time
_active: set[str] = set()
_cache: dict = {}                  # small memo tables, keyed by file mtime so finished runs are parsed once


# ---------------------------------------------------------------------------------------------- models
class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = Field(pattern=r"^(full|sample)$")
    cases: list[str] | None = Field(default=None, max_length=50)
    strict_temporal: bool = False


class RedteamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=2000)


# ---------------------------------------------------------------------------------------------- run data
def validate_run_id(run_id: str) -> str:
    if not _RUN_RX.match(run_id):
        raise HTTPException(422, "invalid run id")
    return run_id


def _run_dir(run_id: str) -> Path:
    validate_run_id(run_id)
    d = RUNS_DIR / run_id
    if not d.is_dir():
        raise HTTPException(404, "unknown run")
    return d


def _read_events(d: Path) -> list[dict]:
    f = d / "trail.jsonl"
    if not f.is_file():
        return []
    st = f.stat()
    key = ("trail", str(f), st.st_mtime_ns, st.st_size)
    if key not in _cache:
        lines = f.read_text(encoding="utf-8").split("\n")
        ev = []
        for ln in lines:
            try:
                ev.append(json.loads(ln))
            except ValueError:  # blank or half-written last line
                pass
        _cache[key] = ev
    return _cache[key]


def load_trail(run_id: str) -> list[dict]:
    return list(_read_events(_run_dir(run_id)))


def _manifest(d: Path) -> dict | None:
    f = d / "manifest.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except ValueError:
        return None


def _summary(run_id: str, d: Path) -> dict:
    m = _manifest(d) or {}
    emits = [e["detail"] for e in _read_events(d) if e["stage"] == "emit"]
    counts = {s: 0 for s in STATUSES}
    matrix = {r: {s: 0 for s in STATUSES} for r in sorted(REPORTED_STATUSES)}
    for x in emits:
        if x.get("status") in counts:
            counts[x["status"]] += 1
            if x.get("reported") in matrix:
                matrix[x["reported"]][x["status"]] += 1
    started = run_id.split("-")[0]
    return {"run_id": run_id, "started": f"{started[:4]}-{started[4:6]}-{started[6:8]}T{started[9:11]}:{started[11:13]}:{started[13:15]}Z",
            "cases": m.get("cases", len(emits)), "counts": counts, "strict_temporal": bool(m.get("strict_temporal")),
            "output_sha256": m.get("output_sha256"), "_matrix": matrix, "_manifest": m}


def _cases(d: Path) -> dict:
    """case_id -> {reported, status, steps, warns, fails} from the trail."""
    out: dict = {}
    for e in _read_events(d):
        cid = e.get("case_id")
        if not cid:
            continue
        c = out.setdefault(cid, {"case_id": cid, "reported": None, "status": None, "steps": 0, "warns": 0, "fails": 0})
        c["warns"] += e["verdict"] == "WARN"
        c["fails"] += e["verdict"] == "FAIL"
        if e["stage"] == "emit":
            c |= {"reported": e["detail"].get("reported"), "status": e["detail"].get("status"), "steps": e["detail"].get("steps", 0)}
    return out


def _output_rows(d: Path, m: dict) -> dict:
    """case_id -> (status, steps) from the run's own output.csv (or the repo-root copy when its hash matches)."""
    f = d / "output.csv"
    if not f.is_file():
        root = REPO / Path(m.get("output", "")).name
        if not (m.get("output") and root.is_file() and pipeline.sha256_file(root) == m.get("output_sha256")):
            return {}
        f = root
    key = ("out", str(f), f.stat().st_mtime_ns)
    if key not in _cache:
        with open(f, encoding="utf-8", newline="") as fh:
            _cache[key] = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(fh)}
    return _cache[key]


# ---------------------------------------------------------------------------------------------- per-case recompute
class _NullTrail:
    def event(self, *a, **k):
        pass


def _facts():
    if "facts" not in _cache:
        _cache["facts"] = evidence.ingest(_NullTrail())[:2]
    return _cache["facts"]


def _ctx(requests_name: str, strict: bool) -> tuple[dict, list[dict]]:
    key = ("ctx", requests_name, strict)
    if key not in _cache:
        facts, coverage = _facts()
        requests = read_csv(DATASET / requests_name)
        ctx = {"identity": identity.build_index(), "facts": facts, "coverage": coverage, "rules": read_csv(DATASET / "deletion_rules.csv"),
               "evidence_index": load_evidence_index(), "offline": True, "strict_temporal": strict, "client": None}
        ctx["orphans"] = orphan.discover(requests, ctx)
        _cache[key] = (ctx, requests)
    return _cache[key]


def _case_state(run_id: str, case_id: str) -> dict:
    """Re-run S2-S5 for ONE case with the real stages (same calls as pipeline.audit_case)."""
    d = _run_dir(run_id)
    m = _manifest(d) or {}
    name = m.get("requests")
    if name not in REQUEST_FILES.values():
        raise HTTPException(404, "unknown run inputs")
    ctx, requests = _ctx(name, bool(m.get("strict_temporal")))
    req = next((r for r in requests if r["case_id"] == case_id), None)
    if req is None:
        raise HTTPException(404, "unknown case")
    it = intent.classify(req["request_text"], offline=True)
    subject = linked = None
    if it.label == "DELETE":
        subject = identity.resolve(req["email"], req["audit_at"], ctx["identity"])
        if subject:
            linked = reasoning.link(subject, ctx["facts"], req["requested_at"], req["audit_at"], ctx["strict_temporal"])
            linked = orphan.extend(linked, ctx["orphans"].get(case_id, ()), ctx["facts"], req["audit_at"])
    return {"req": req, "intent": it, "subject": subject, "linked": linked, "ctx": ctx, "dir": d, "manifest": m}


# ---------------------------------------------------------------------------------------------- app
def create_app() -> FastAPI:
    app = FastAPI(title="Ghost Data console API", docs_url=None, redoc_url=None, openapi_url=None)

    def reject(status: int, detail: str) -> JSONResponse:
        return JSONResponse({"detail": detail}, status_code=status)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path, origin = request.url.path, request.headers.get("origin")
        if request.headers.get("host", "") not in HOSTS:
            return reject(403, "forbidden host")
        if origin is not None and origin not in ORIGINS:
            return reject(403, "forbidden origin")
        cors = {} if (origin is None or path == "/api/token") else {
            "Access-Control-Allow-Origin": origin, "Vary": "Origin",
            "Access-Control-Allow-Headers": "Content-Type, X-Console-Token", "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE"}
        if request.method == "OPTIONS":
            resp = JSONResponse({}, status_code=204 if cors else 403)
        elif request.method not in ("GET", "POST", "PUT", "DELETE"):
            resp = reject(405, "method not allowed")
        elif request.method != "GET" and not secrets.compare_digest(request.headers.get("x-console-token", "").encode(), TOKEN.encode()):
            resp = reject(401, "missing or invalid token")
        elif request.method in ("POST", "PUT") and not request.headers.get("content-length", "").isdigit():
            resp = reject(411, "length required")
        elif request.method in ("POST", "PUT") and int(request.headers["content-length"]) > MAX_BODY:
            resp = reject(413, "body too large")
        else:
            resp = await call_next(request)
        resp.headers.update(cors)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.exception_handler(RequestValidationError)
    async def _invalid(_r, _e):
        return reject(422, "invalid request")  # never echo the input back

    @app.exception_handler(HTTPException)
    async def _http(_r, e: HTTPException):
        return reject(e.status_code, str(e.detail))

    @app.exception_handler(Exception)
    async def _boom(_r, _e):
        return reject(500, "internal error")

    RunId = PathParam(pattern=RUN_ID)
    CaseId = PathParam(pattern=CASE_ID)

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": VERSION}

    @app.get("/api/token")
    def token():
        return {"token": TOKEN}

    @app.get("/api/runs")
    def runs():
        out = []
        for d in sorted(RUNS_DIR.glob("*") if RUNS_DIR.is_dir() else [], reverse=True):
            if d.is_dir() and _RUN_RX.match(d.name) and (d / "manifest.json").is_file():
                s = _summary(d.name, d)
                out.append({k: v for k, v in s.items() if not k.startswith("_")})
        return out

    @app.post("/api/runs")
    def start_run(body: RunRequest):
        bad = [c for c in body.cases or [] if not _CASE_RX.match(c)]
        if bad:
            raise HTTPException(422, "invalid case id")
        if not _lock.acquire(blocking=False):
            raise HTTPException(409, "a run is already in progress")
        run_id = new_run_id()
        try:
            (RUNS_DIR / run_id).mkdir(parents=True)  # so the SSE tail can attach before the trail file exists
            _active.add(run_id)
            requests_path = DATASET / REQUEST_FILES[body.dataset]

            def work():
                try:
                    pipeline.run(requests_path, RUNS_DIR / run_id / "output.csv", runs_dir=RUNS_DIR, cases=body.cases,
                                 offline=True, strict_temporal=body.strict_temporal, run_id=run_id)
                except Exception:  # GateFailure already wrote its trail; anything else must not kill the server
                    pass
                finally:
                    _active.discard(run_id)
                    _lock.release()

            threading.Thread(target=work, daemon=True).start()
        except BaseException:
            _active.discard(run_id)
            _lock.release()
            raise
        return {"run_id": run_id}

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str = RunId):
        d = _run_dir(run_id)
        s = _summary(run_id, d)
        return scrub(s["_manifest"] | {k: s[k] for k in ("run_id", "started", "counts", "output_sha256")}
                     | {"claim_matrix": {"reported": s["_matrix"]}, "running": run_id in _active})

    @app.get("/api/runs/{run_id}/events")
    async def events(request: Request, run_id: str = RunId, start: int = Query(0, alias="from", ge=0, le=10_000_000)):
        d = _run_dir(run_id)
        trail = d / "trail.jsonl"

        async def gen():
            sent, offset, ticks = 0, 0, 0
            while ticks * 0.25 < SSE_MAX_SECONDS and not await request.is_disconnected():
                finished = run_id not in _active  # read this BEFORE the file so no trailing event is lost
                if trail.is_file():
                    with open(trail, "rb") as f:
                        f.seek(offset)
                        chunk = f.read()
                    nl = chunk.rfind(b"\n") + 1  # only whole lines
                    offset += nl
                    for ln in chunk[:nl].decode("utf-8").splitlines():
                        if ln.strip():
                            if sent >= start:
                                yield f"data: {ln}\n\n"
                            sent += 1
                if finished:
                    yield "event: done\ndata: {}\n\n"
                    return
                ticks += 1
                await asyncio.sleep(0.25)

        return StreamingResponse(gen(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.get("/api/runs/{run_id}/cases")
    def cases(run_id: str = RunId, status: str | None = Query(None, pattern=r"^[A-Z_]{1,20}$"),
              reported: str | None = Query(None, pattern=r"^[A-Z_]{1,20}$"), q: str | None = Query(None, pattern=r"^[a-z0-9_]{0,12}$")):
        rows = [c for c in _cases(_run_dir(run_id)).values()
                if (not status or c["status"] == status) and (not reported or c["reported"] == reported)
                and (not q or c["case_id"].startswith(q))]
        return sorted(rows, key=lambda c: case_sort_key(c["case_id"]))

    @app.get("/api/runs/{run_id}/cases/{case_id}")
    def case_detail(run_id: str = RunId, case_id: str = CaseId):
        st = _case_state(run_id, case_id)
        req, it, subject = st["req"], st["intent"], st["subject"]
        row = _cases(st["dir"]).get(case_id)
        if row is None:
            raise HTTPException(404, "case not in this run")
        _, steps = _output_rows(st["dir"], st["manifest"]).get(case_id, (None, []))
        return scrub({"case_id": case_id, "reported": row["reported"], "reported_at": req["reported_at"],
                      "requested_at": req["requested_at"], "audit_at": req["audit_at"], "status": row["status"],
                      "intent": {"label": it.label, "source": it.source, "flags": list(it.flags)},
                      "identity": {"user_id": subject.user_id if subject else None,
                                   "email_count": len(subject.emails) if subject else 0,
                                   "phone_count": len(subject.phones) if subject else 0},
                      "steps": steps, "trail": [e for e in _read_events(st["dir"]) if e.get("case_id") == case_id]})

    @app.get("/api/runs/{run_id}/cases/{case_id}/timeline")
    def timeline(run_id: str = RunId, case_id: str = CaseId):
        st = _case_state(run_id, case_id)
        req, linked = st["req"], st["linked"]
        aud = ts(req["audit_at"])
        res = linked.resources if linked else frozenset()
        items = [{"observed_at": f.observed_at, "captured_at": f.captured_at, "system_id": f.system_id, "resource_id": f.resource_id,
                  "observation": f.observation, "evidence_id": f.evidence_id, "is_claim": f.is_claim, "citable": ts(f.captured_at) <= aud}
                 for f in sorted((f for f in st["ctx"]["facts"] if (f.system_id, f.resource_id) in res),
                                 key=lambda f: (ts(f.observed_at), f.system_id, f.resource_id, f.evidence_id))]
        return scrub({"requested_at": req["requested_at"], "reported_at": req["reported_at"], "audit_at": req["audit_at"], "items": items})

    @app.get("/api/runs/{run_id}/cases/{case_id}/identity")
    def identity_graph(run_id: str = RunId, case_id: str = CaseId):
        st = _case_state(run_id, case_id)
        subject, linked, req = st["subject"], st["linked"], st["req"]
        if not subject:
            return {"nodes": [], "edges": []}
        row, log = st["ctx"]["identity"]["users"][subject.user_id]
        now = identity._as_of(row, log, ts(req["audit_at"]))[0]
        cur_email = now["email"].lower()
        cur_hash = hashlib.sha256(now["email"].encode("utf-8")).hexdigest()
        cur_phone = re.sub(r"\D", "", now["phone"])
        nodes = [{"id": "user", "kind": "user", "label": subject.user_id, "current": True}]
        edges, ids = [], {("user_id", subject.user_id): "user"}

        def add(kind, key, label, current, flavour):
            nid = f"{kind}_{len([n for n in nodes if n['kind'] == kind])}"
            ids[(flavour, key)] = nid
            nodes.append({"id": nid, "kind": kind, "label": mask(label), "current": current})
            edges.append({"from": "user", "to": nid, "label": "has"})

        for e in sorted(subject.emails):
            add("email", e.lower(), e, e.lower() == cur_email, "email")
        for p in sorted(subject.phones):
            add("phone", re.sub(r"\D", "", p), p, re.sub(r"\D", "", p) == cur_phone, "phone")
        for h in sorted(subject.email_hashes):
            add("hash", h.lower(), h, h.lower() == cur_hash, "email_hash")
        for sys_id, res_id in sorted(linked.resources):
            rid = f"res:{sys_id}/{res_id}"
            nodes.append({"id": rid, "kind": "resource", "label": f"{sys_id}/{res_id}", "current": True})
            via = next((ids[k] for f in st["ctx"]["facts"] if (f.system_id, f.resource_id) == (sys_id, res_id)
                        for k in f.subject_keys if k in ids), "user")  # orphans carry no key: linked through the user
            edges.append({"from": via, "to": rid, "label": "links"})
        return scrub({"nodes": nodes, "edges": edges})

    @app.get("/api/runs/{run_id}/usage")
    def usage(run_id: str = RunId):
        d = _run_dir(run_id)
        m = _manifest(d) or {}
        rows, f = [], d / "usage.jsonl"
        if f.is_file():
            rows = [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        by: dict = {}
        for u in rows:
            t = by.setdefault(u["model"], {"model": u["model"], "calls": 0, "cached": 0, "tokens": 0})
            t["calls"] += 1
            t["cached"] += bool(u.get("cached"))
            t["tokens"] += u.get("total_tokens", 0)
        same = [x for x in (_manifest(p) for p in RUNS_DIR.glob("*") if _RUN_RX.match(p.name) and p.is_dir()) if x
                and (x.get("requests"), x.get("strict_temporal"), x.get("offline"), x.get("inputs"), x.get("cases"))
                == (m.get("requests"), m.get("strict_temporal"), m.get("offline"), m.get("inputs"), m.get("cases"))
                and x.get("output_sha256")]
        det = None if len(same) < 2 else len({x["output_sha256"] for x in same}) == 1  # null until a run has been repeated
        return {"calls": len(rows), "cached": sum(t["cached"] for t in by.values()), "tokens": sum(t["tokens"] for t in by.values()),
                "by_model": list(by.values()), "output_sha256": m.get("output_sha256"), "deterministic": det}

    @app.post("/api/redteam")
    def redteam(body: RedteamRequest):
        it = intent.classify(body.text, offline=True)
        injected = "injection_marker" in it.flags
        return scrub({"label": it.label, "confidence": it.confidence, "source": it.source, "flags": list(it.flags),
                      "status_would_be": "changed" if injected and it.label == "DELETE" else "unchanged"})

    deps = SimpleNamespace(runs_dir=RUNS_DIR, load_trail=load_trail, validate_run_id=validate_run_id, mask_text=mask_text,
                           scrub=scrub, token_ok=lambda t: secrets.compare_digest((t or "").encode(), TOKEN.encode()))
    for name in ("ask", "settings_api", "metrics_api"):  # optional extension modules, each exposes register(app, deps)
        try:
            import importlib
            importlib.import_module(f".{name}", __package__).register(app, deps)
        except ModuleNotFoundError as e:
            if e.name != f"{__package__}.{name}":
                raise  # a real missing dependency inside the module, not an absent module
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
