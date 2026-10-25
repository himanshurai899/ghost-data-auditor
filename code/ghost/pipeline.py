"""Gated pipeline: S0 Load -G1- S1 Ingest -G2- per case [S2 Intent -G3- S3 Identity -G4- S4 Link -G5-
S5 State, S6 Policy, S7 Plan -G6-] S8 Emit -G7- (architecture.md §4). Used by the CLI and the console API."""
import hashlib
import json
import subprocess
from pathlib import Path

from . import ev_page, evidence, identity, intent, llm, orphan, planner, reasoning
from .audit import Trail, new_run_id
from .contract import (DATASET, REPO, check_inputs, load_evidence_index, load_requests, read_csv, validate_output,
                       validate_row, write_output, ts)

MAX_QUARANTINE_SHARE = 0.10


class GateFailure(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _write_usage(trail_dir: Path, usage_rows) -> None:
    with open(Path(trail_dir) / "usage.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for u in usage_rows:
            f.write(json.dumps(u, sort_keys=True) + "\n")


def run(requests_path: Path, out_path: Path, runs_dir: Path = REPO / "runs", cases=None, offline: bool = True,
        strict_temporal: bool = False) -> dict:
    requests_path, out_path = Path(requests_path), Path(out_path)
    trail = Trail(runs_dir, new_run_id())
    manifest = {"run_id": trail.run_id, "git_sha": _git_sha(), "offline": offline, "strict_temporal": strict_temporal, "models": llm.models(),
                "requests": requests_path.name}

    def abort(gate, summary, errors):
        trail.event("gate", summary, gate=gate, verdict="FAIL", detail={"errors": errors[:20]})
        trail.close(manifest | {"aborted_at": gate})
        raise GateFailure(f"{gate}: {summary}")

    # S0 Load + G1
    try:
        requests = load_requests(requests_path)
        errors = check_inputs(requests)
    except (ValueError, KeyError) as e:
        requests, errors = [], [str(e)]
    if cases:
        wanted = set(cases)
        errors += [f"unknown case {c}" for c in sorted(wanted - {r["case_id"] for r in requests})]
        all_requests, requests = requests, [r for r in requests if r["case_id"] in wanted]
    else:
        all_requests = requests
    if errors:
        abort("G1", f"Input gate failed: {errors[0]}", errors)
    trail.event("load", f"Loaded {len(requests)} requests with valid schema and timestamps.", gate="G1", verdict="PASS")

    # S1 Ingest + G2
    facts, coverage, quarantined = evidence.ingest(trail)
    n_files = len(read_csv(DATASET / "evidence_files.csv"))
    if len(quarantined) > MAX_QUARANTINE_SHARE * n_files:
        abort("G2", f"{len(quarantined)} of {n_files} evidence files quarantined.", [f"{q}: {r}" for q, r in quarantined])
    trail.event("ingest", f"Ingested {len(facts)} facts from {n_files} evidence files; {len(quarantined)} quarantined.",
                gate="G2", verdict="PASS" if facts else "WARN")

    ctx = {"identity": identity.build_index(), "facts": facts, "coverage": coverage, "rules": read_csv(DATASET / "deletion_rules.csv"),
           "evidence_index": load_evidence_index(), "offline": offline,
           "strict_temporal": strict_temporal}
    ctx["orphans"] = orphan.discover(all_requests, ctx)
    rows, g6_failures = [], 0
    for req in requests:
        status, steps = audit_case(req, ctx, trail)
        errs = validate_row(req["case_id"], status, steps, req["audit_at"], ctx["evidence_index"])
        if errs:
            g6_failures += 1
        trail.event("contract", errs[0] if errs else "Steps satisfy the output contract.", case_id=req["case_id"],
                    gate="G6", verdict="FAIL" if errs else "PASS", detail={"errors": errs})
        trail.event("emit", f"Audited {status} with {len(steps)} steps (workflow claimed {req['reported_status']}).",
                    case_id=req["case_id"], evidence_ids=sorted({s["evidence_id"] for s in steps if s["evidence_id"]}),
                    detail={"reported": req["reported_status"], "status": status, "steps": len(steps)})
        rows.append((req["case_id"], status, steps))

    # S8 Emit + G7
    write_output(rows, out_path)
    g7 = validate_output(out_path, requests_path, None if not cases else set(cases))
    if g6_failures:
        g7.append(f"{g6_failures} cases failed G6")
    usage = list(getattr(ev_page._client, "usage", []))  # the Client configured for the run, if any
    _write_usage(trail.dir, usage)
    manifest |= {"llm_calls": len(usage), "llm_tokens": sum(u.get("total_tokens", 0) for u in usage)}
    manifest |= {"cases": len(rows), "g6_failures": g6_failures, "output": out_path.name,
                 "output_sha256": sha256_file(out_path),
                 "inputs": {p.name: sha256_file(p) for p in [requests_path, DATASET / "evidence_files.csv",
                                                             DATASET / "deletion_rules.csv"]}}
    trail.event("release", g7[0] if g7 else f"Output valid: {len(rows)} rows, numeric order, contract satisfied.",
                gate="G7", verdict="FAIL" if g7 else "PASS", detail={"errors": g7[:20]})
    trail.close(manifest)
    if g7:
        raise GateFailure(f"G7: {g7[0]}")
    return manifest


def audit_case(req: dict, ctx: dict, trail: Trail) -> tuple[str, list[dict]]:
    cid = req["case_id"]

    # S2 Intent + G3
    it = intent.classify(req["request_text"], offline=ctx["offline"])
    if it.label == "UNKNOWN" or it.flags:
        trail.event("intent", f"Intent {it.label} (source={it.source}, flags={list(it.flags)}); "
                              "no deletion authorized without a confident DELETE.", case_id=cid, gate="G3", verdict="WARN")
    else:
        trail.event("intent", f"Intent {it.label} (source={it.source}, confidence={it.confidence:.2f}).",
                    case_id=cid, gate="G3", verdict="PASS")
    if it.label != "DELETE":
        return "NOT_APPLICABLE", []

    # S3 Identity + G4
    subject = identity.resolve(req["email"], req["audit_at"], ctx["identity"])
    trail.event("identity", "Request email matched no identity as of audit_at." if subject is None else
                f"Resolved {subject.user_id} with {len(subject.emails)} emails, {len(subject.phones)} phones.",
                case_id=cid, gate="G4", verdict="WARN" if subject is None else "PASS")

    # S4 Link + G5 (hard temporal filter inside reasoning.link)
    linked = (reasoning.link(subject, ctx["facts"], req["requested_at"], req["audit_at"], ctx["strict_temporal"])
              if subject else reasoning.Linked(frozenset(), (), frozenset()))
    if subject:
        linked = orphan.extend(linked, ctx.get("orphans", {}).get(cid, ()), ctx["facts"], req["audit_at"])
    facts = list(linked.facts)
    breach = any(ts(f.captured_at) > ts(req["audit_at"]) for f in facts)  # the hard filter makes this impossible
    trail.event("link", f"Linked {len(linked.resources)} resources, {len(facts)} citable facts "
                        f"({len(linked.late_only)} discovered only via files captured after audit_at; "
                        f"strict_temporal={ctx['strict_temporal']}).", case_id=cid, gate="G5",
                verdict="WARN" if breach else "PASS")

    # S5-S7
    verdicts = reasoning.evaluate(facts, ctx["rules"], req["audit_at"], ctx["coverage"], ctx["facts"])
    try:
        return planner.plan(verdicts)
    except ValueError as e:  # one unplannable case must not abort the run
        trail.event("plan", f"Planner could not plan ({e}); emitting NOT_APPLICABLE placeholder.",
                    case_id=cid, verdict="WARN")
        return "NOT_APPLICABLE", []
