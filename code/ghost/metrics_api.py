"""Read-only dashboard / cost / evidence-chain endpoints (docs/ui_redesign.md). Plugs into api.py via register(app, deps).

Everything is derived from runs/<id>/ artifacts and the dataset files; unknown values are null, never invented.
Evidence tiers: A direct row, B omission from a table-level snapshot, C claim only, D captured after audit_at, X none.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Path as PathParam

from .contract import DATASET, read_csv, ts

CODE = Path(__file__).resolve().parents[1]
PRICING, LEDGER = CODE / "config" / "pricing.json", CODE / "data" / "usage_cache_build.jsonl"
BASE = {"A": 100, "B": 75, "C": 40, "D": 10, "X": 0}
LABEL = {"A": "Direct", "B": "Inferred", "C": "Claim", "D": "Late", "X": "None"}
FAMILY = {"REPORT_REMAINING_RECORD": "records", "REPORT_EXPOSED_PII": "pii", "REPORT_ACTIVE_DATA_FLOW": "flows", "REPORT_RESTORE_RISK": "restores"}
OBS_FOR_STATE = {"PRESENT": {"PRESENT"}, "ABSENT": {"ABSENT"}, "REDACTED": {"REDACTED"}, "ANONYMIZED": {"ANONYMIZED"},
                 "ACTIVE": {"FLOW_ACTIVE", "RESTORE_OPEN"}, "DISABLED": {"FLOW_DISABLED"}, "BLOCKED": {"RESTORE_BLOCKED"}}
_memo: dict = {}
api = None  # ghost.api module object, bound in register() (works for `python -m ghost.api`, where it is __main__)


# ---------------------------------------------------------------------------------------------- shared tier logic
def _manifest_captured() -> dict:
    if "files" not in _memo:
        _memo["files"] = {r["file_id"]: r["captured_at"] for r in read_csv(DATASET / "evidence_files.csv")}
    return _memo["files"]


def _fact_index() -> dict:
    """(evidence_id, system, resource) -> non-claim facts; resource -> facts; built once from the cached ingest."""
    if "idx" not in _memo:
        facts, coverage = api._facts()
        rows, by_res = defaultdict(list), defaultdict(list)
        for f in facts:
            by_res[(f.system_id, f.resource_id)].append(f)
            if not f.is_claim:
                rows[(f.evidence_id, f.system_id, f.resource_id)].append(f)
        _memo["idx"] = (rows, by_res, {c.evidence_id: c for c in coverage})
    return _memo["idx"]


def _score(tier: str, captured: str | None, audit: str) -> int:
    pen = 0 if captured is None else min(20, max(0, (ts(audit) - ts(captured)).days))
    return 0 if tier == "X" else max(0, BASE[tier] - pen)


def _step_tier(step: dict, audit: str) -> dict:
    """Tier, timestamps and a plain sentence for one output step. Same logic for the chain and the dashboard mix."""
    rows, by_res, cov = _fact_index()
    eid, sys_id, res, state = step["evidence_id"], step["system_id"], step["resource_id"], step["state"]
    if not eid:
        why = ("Future step: remediation is proposed, no evidence by design." if step["phase"] != "FINDING" else
               f"Finding on {res} rests on a workflow claim only; no file row exists.")
        return {"tier": "X" if step["phase"] != "FINDING" else "C", "captured_at": None, "observed_at": None, "why": why}
    cap = _manifest_captured().get(eid)
    if cap is None:  # activity or audit id: a claim, not a file
        act = next((f for f in by_res.get((sys_id, res), ()) if f.evidence_id == eid), None)
        return {"tier": "C", "captured_at": act.captured_at if act else None, "observed_at": act.observed_at if act else None,
                "why": f"{eid} is an activity claim about {res}; claims never prove state."}
    days = (ts(audit) - ts(cap)).days
    if ts(cap) > ts(audit):
        return {"tier": "D", "captured_at": cap, "observed_at": None,
                "why": f"{eid} was captured {cap[:10]}, after the audit; discovery only."}
    ago = f"{days} day{'s' if days != 1 else ''} before the audit"
    hit = rows.get((eid, sys_id, res))
    if hit:
        f = sorted(hit, key=lambda f: (f.observed_at, f.observation))[-1]
        match = next((h for h in hit if h.observation in OBS_FOR_STATE.get(state, ())), f)
        return {"tier": "A", "captured_at": cap, "observed_at": match.observed_at,
                "why": f"Row for {res} in file {eid} captured {cap[:10]}, {ago}, shows it {match.observation}."}
    c = cov.get(eid)
    return {"tier": "B", "captured_at": cap, "observed_at": c.observed_at if c else None,
            "why": f"File {eid} captured {cap[:10]}, {ago}, is a table-level snapshot of {sys_id} with no row for {res}, so it is absent."}


# ---------------------------------------------------------------------------------------------- run helpers
def _newest(runs_dir: Path) -> str:
    for d in sorted(runs_dir.glob("*") if runs_dir.is_dir() else [], reverse=True):
        if d.is_dir() and api._RUN_RX.match(d.name) and (d / "manifest.json").is_file():
            return d.name
    raise HTTPException(404, "no runs")


def _requests(m: dict) -> dict:
    name = m.get("requests")
    if name not in api.REQUEST_FILES.values():
        raise HTTPException(404, "unknown run inputs")
    key = ("req", name)
    if key not in _memo:
        _memo[key] = {r["case_id"]: r for r in read_csv(DATASET / name)}
    return _memo[key]


def _duration(d: Path) -> int | None:
    f = d / "trail.jsonl"
    try:
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return max(0, round((datetime.fromisoformat(json.loads(lines[-1])["ts"]) - datetime.fromisoformat(json.loads(lines[0])["ts"])).total_seconds()))
    except (OSError, ValueError, IndexError, KeyError):
        return None


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def _mix(run_id: str, d: Path, m: dict) -> dict:
    key = ("mix", run_id)
    if key not in _memo:
        reqs, rows = _requests(m), api._output_rows(d, m)
        _, by_res, _ = _fact_index()
        mix, late = Counter(), set()
        for cid, (_, steps) in rows.items():
            audit = reqs[cid]["audit_at"]
            for s in steps:
                if s["evidence_id"]:
                    mix[_step_tier(s, audit)["tier"]] += 1
                for f in by_res.get((s["system_id"], s["resource_id"]), ()):
                    if ts(f.captured_at) > ts(audit):
                        late.add((cid, f.evidence_id))
        mix["D"] += len(late)  # distinct late files on resources the case has steps for (discovery only)
        _memo[key] = {t: mix[t] for t in "ABCD"}
    return _memo[key]


def _cost_rows(rows: list[dict], pricing: dict) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups[(r.get("provider", "nvidia"), r["model"], r.get("role"))].append(r)

    def agg(rs, rates):
        s = lambda k: None if any(r.get(k) is None for r in rs) else sum(r[k] for r in rs)
        i, o = s("prompt_tokens"), s("output_tokens")
        cost = None if not rates or rates.get("input") is None or rates.get("output") is None or i is None or o is None else (i * rates["input"] + o * rates["output"]) / 1e6
        return {"calls": len(rs), "cached": sum(1 for r in rs if r.get("cached")), "tokens_in": i, "tokens_out": o, "est_cost_usd": cost}

    by_model = [{"provider": p, "model": mdl, "role": role} | agg(rs, pricing["models"].get(mdl)) for (p, mdl, role), rs in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0]))]
    return {"by_model": by_model, "calls": len(rows), "cached": sum(1 for r in rows if r.get("cached")),
            "tokens_in": None if any(b["tokens_in"] is None for b in by_model) else sum(b["tokens_in"] for b in by_model),
            "tokens_out": None if any(b["tokens_out"] is None for b in by_model) else sum(b["tokens_out"] for b in by_model),
            "est_cost_usd": 0.0 if not rows else (None if any(b["est_cost_usd"] is None for b in by_model) else sum(b["est_cost_usd"] for b in by_model))}


# ---------------------------------------------------------------------------------------------- endpoints
def register(app, deps):
    global api
    api = sys.modules[deps.load_trail.__module__]
    RunId, CaseId = PathParam(pattern=api.RUN_ID), PathParam(pattern=api.CASE_ID)
    scrub, runs_dir = deps.scrub, deps.runs_dir

    def run_of(run_id: str | None):
        rid = deps.validate_run_id(run_id) if run_id else _newest(runs_dir)
        d = api._run_dir(rid)
        return rid, d, api._manifest(d) or {}

    @app.get("/api/dashboard")
    def dashboard(run_id: str | None = None):
        rid, d, m = run_of(run_id)
        s = api._summary(rid, d)
        matrix = s["_matrix"]
        rows = api._output_rows(d, m)
        reported_complete = sum(matrix["COMPLETE"].values())
        ghost = matrix["COMPLETE"]["INCOMPLETE"]
        fbs: dict = {}
        for _, steps in rows.values():
            for st in steps:
                fam = FAMILY.get(st["operation"]) if st["phase"] == "FINDING" else None
                if fam:
                    fbs.setdefault(st["system_id"], dict.fromkeys(("records", "pii", "flows", "restores"), 0))[fam] += 1
        gates: dict = {}
        for e in api._read_events(d):
            if e.get("gate"):
                gates.setdefault(e["gate"], Counter())[e["verdict"]] += 1
        runs = []
        for p in sorted(runs_dir.glob("*"), reverse=True):
            if len(runs) < 20 and p.is_dir() and api._RUN_RX.match(p.name) and (p / "manifest.json").is_file():
                x = api._summary(p.name, p)
                runs.append({k: x[k] for k in ("run_id", "started", "cases", "counts", "output_sha256", "strict_temporal")} | {"duration_s": _duration(p)})
        return scrub({
            "run_id": rid, "cases": s["cases"], "counts": s["counts"], "claim_matrix": {"reported": matrix},
            "ghosts": {"count": ghost, "of": reported_complete, "pct": round(100 * ghost / reported_complete, 1) if reported_complete else None},
            "findings_by_system": [{"system_id": k} | v for k, v in sorted(fbs.items())],
            "gates": [{"gate": g, "pass": c["PASS"], "warn": c["WARN"], "fail": c["FAIL"]}
                      for g, c in sorted(gates.items(), key=lambda kv: int(kv[0][1:]) if kv[0][1:].isdigit() else 99)],
            "runs": runs, "evidence_mix": _mix(rid, d, m) if rows else {t: 0 for t in "ABCD"},
            "llm_calls": m.get("llm_calls"), "offline": m.get("offline")})

    @app.get("/api/metrics/cost")
    def cost(run_id: str | None = None):
        rid, d, m = run_of(run_id)
        pricing = json.loads(PRICING.read_text(encoding="utf-8"))
        usage, build = _jsonl(d / "usage.jsonl"), _jsonl(LEDGER)
        run, cb = _cost_rows(usage, pricing), _cost_rows(build, pricing)
        reqs = m.get("cases") or m.get("requests_count")
        tot_in, tot_out = run["tokens_in"], run["tokens_out"]
        total = None if tot_in is None or tot_out is None else tot_in + tot_out
        buckets = Counter(str(u["ts"])[:16] for u in usage if u.get("ts"))
        all_runs = []
        for p in sorted(runs_dir.glob("*"), reverse=True)[:20]:
            x = api._manifest(p) if p.is_dir() and api._RUN_RX.match(p.name) else None
            if x:
                all_runs.append({"run_id": p.name, "calls": x.get("llm_calls"), "tokens": x.get("llm_tokens"), "duration_s": _duration(p)})
        return scrub({
            "run": {"run_id": rid, "requests": reqs, "calls": run["calls"], "cached": run["cached"], "live": run["calls"] - run["cached"],
                    "tokens_in": tot_in, "tokens_out": tot_out,
                    "avg_tokens_per_request": None if total is None or not reqs else round(total / reqs, 1),
                    "est_cost_usd": run["est_cost_usd"], "billed_usd": 0, "by_model": run["by_model"],
                    "calls_over_time": [{"t": t, "calls": n} for t, n in sorted(buckets.items())]},
            "cache_build": {"calls": cb["calls"], "by_model": cb["by_model"]},
            "all_runs": all_runs,
            "pricing": {"source": pricing.get("source"), "rates_known": any(r.get("input") is not None and r.get("output") is not None for r in pricing["models"].values())},
            "notes": [
                "The offline run is deterministic code over cached evidence facts and makes zero model calls.",
                "The page-cache build (Nemotron Parse over the rendered screenshots) was a one-time cost outside the per-request numbers; its token counts were not retained and are null, not estimated.",
                "billed_usd is 0 because every call used the NVIDIA build free tier; it is stated from the project's setup, not measured from a billing API.",
                "Estimated cost is null until reference per-token rates are recorded in pricing.json."]})

    @app.get("/api/runs/{run_id}/cases/{case_id}/evidence")
    def evidence_chain(run_id: str = RunId, case_id: str = CaseId):
        d = api._run_dir(deps.validate_run_id(run_id))
        m = api._manifest(d) or {}
        reqs = _requests(m)
        if case_id not in reqs:
            raise HTTPException(404, "unknown case")
        if case_id not in api._output_rows(d, m):
            raise HTTPException(404, "case not in this run")
        _, steps = api._output_rows(d, m)[case_id]
        audit = reqs[case_id]["audit_at"]
        chain, used, tiers = [], defaultdict(list), {}
        for s in steps:
            t = _step_tier(s, audit)
            chain.append({"step_no": s["step_no"], "phase": s["phase"], "operation": s["operation"], "system_id": s["system_id"],
                          "resource_id": s["resource_id"], "state": s["state"], "evidence_id": s["evidence_id"], "tier": t["tier"],
                          "tier_label": LABEL[t["tier"]], "score": _score(t["tier"], t["captured_at"], audit),
                          "captured_at": t["captured_at"], "observed_at": t["observed_at"],
                          "citable": t["tier"] in ("A", "B"), "why": t["why"]})
            if s["evidence_id"]:
                used[s["evidence_id"]].append(s["step_no"])
                best = tiers.get(s["evidence_id"])
                if best is None or BASE[t["tier"]] > BASE[best[0]]:
                    tiers[s["evidence_id"]] = (t["tier"], _score(t["tier"], t["captured_at"], audit))
        # discovery-only evidence: every fact on the case's linked resources that is late (D) or a claim (C) and not cited
        st = api._case_state(run_id, case_id)
        linked = st["linked"]
        if linked:
            _, by_res, _ = _fact_index()
            for res in sorted(linked.resources):
                for f in by_res.get(res, ()):
                    if f.evidence_id in tiers:
                        continue
                    late = ts(f.captured_at) > ts(audit)
                    if late or f.is_claim:
                        tier = "D" if late else "C"
                        tiers[f.evidence_id] = (tier, _score(tier, f.captured_at, audit))
        ranking = [{"evidence_id": e, "tier": t, "score": sc, "used_by_steps": used.get(e, [])}
                   for e, (t, sc) in sorted(tiers.items(), key=lambda kv: (-kv[1][1], kv[0]))]
        summary = Counter(c["tier"] for c in chain)
        return scrub({"chain": chain, "ranking": ranking, "summary": {t: summary[t] for t in "ABCDX"}})
