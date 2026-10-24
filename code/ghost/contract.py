"""Output contract: constants, loaders, and the validator behind gates G1, G6, G7.

Single source of truth for the problem statement's rules. The pipeline, the
scorer, and scripts/gate.py all import from here.
"""
import csv
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "dataset"

# Spec table order. Index = within-phase sort rank (problem_statement.md "Allowed Operations").
OPS = [
    ("FINDING", "REPORT_REMAINING_RECORD", "PRESENT"),
    ("FINDING", "REPORT_EXPOSED_PII", "PRESENT"),
    ("FINDING", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
    ("FINDING", "REPORT_RESTORE_RISK", "ACTIVE"),
    ("REMEDIATION", "DISABLE_DATA_FLOW", "DISABLED"),
    ("REMEDIATION", "BLOCK_RESTORE", "BLOCKED"),
    ("REMEDIATION", "DELETE_RECORD", "ABSENT"),
    ("REMEDIATION", "REDACT_RECORD", "REDACTED"),
    ("REMEDIATION", "ANONYMIZE_RECORD", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_RECORD_ABSENT", "ABSENT"),
    ("VERIFICATION", "VERIFY_RECORD_PRESENT", "PRESENT"),
    ("VERIFICATION", "VERIFY_RECORD_REDACTED", "REDACTED"),
    ("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
    ("VERIFICATION", "VERIFY_RESTORE_BLOCKED", "BLOCKED"),
]
PHASES = ["FINDING", "REMEDIATION", "VERIFICATION"]
OP_PHASE = {op: ph for ph, op, _ in OPS}
OP_STATE = {op: st for _, op, st in OPS}
OP_RANK = {op: i for i, (_, op, _) in enumerate(OPS)}
STATUSES = ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")
STEP_KEYS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}

REQUEST_HEADER = ["case_id", "email", "requested_at", "reported_status", "reported_at", "audit_at", "request_text"]
OUTPUT_HEADER = ["case_id", "deletion_status", "steps_json"]
REPORTED_STATUSES = {"COMPLETE", "PARTIALLY_COMPLETE", "NOT_STARTED"}


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def case_sort_key(case_id: str) -> int:
    # Numeric, not lexicographic: case_100 sorts after case_33 (dataset_facts F-002).
    return int(case_id.split("_", 1)[1])


def read_csv(path: Path, header: list[str] | None = None) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if header is not None and reader.fieldnames != header:
            raise ValueError(f"{path.name}: header {reader.fieldnames} != {header}")
        return list(reader)


def load_requests(path: Path) -> list[dict]:
    return read_csv(path, REQUEST_HEADER)


def load_evidence_index() -> dict[str, datetime]:
    """Every citable id -> the time it came into existence (file capture, event, audit change)."""
    index = {r["file_id"]: ts(r["captured_at"]) for r in read_csv(DATASET / "evidence_files.csv")}
    index |= {r["activity_id"]: ts(r["event_time"]) for r in read_csv(DATASET / "system_activity.csv")}
    index |= {r["audit_id"]: ts(r["event_time"]) for r in read_csv(DATASET / "user_audit_log.csv")}
    return index


def step_sort_key(step: dict) -> tuple:
    return (PHASES.index(step["phase"]), OP_RANK[step["operation"]], step["system_id"], step["resource_id"])


def finalize_steps(steps: list[dict]) -> list[dict]:
    """Sort into contract order and number from 1. Planner output goes through here."""
    ordered = sorted(steps, key=step_sort_key)
    return [{**s, "step_no": i} for i, s in enumerate(ordered, 1)]


# ---------------------------------------------------------------- G1: inputs

def check_inputs(requests: list[dict]) -> list[str]:
    errors, seen = [], set()
    for r in requests:
        cid = r["case_id"]
        if cid in seen:
            errors.append(f"{cid}: duplicate case_id")
        seen.add(cid)
        if r["reported_status"] not in REPORTED_STATUSES:
            errors.append(f"{cid}: unknown reported_status {r['reported_status']!r}")
        try:
            case_sort_key(cid)
            if ts(r["requested_at"]) > ts(r["audit_at"]):
                errors.append(f"{cid}: requested_at after audit_at")
        except ValueError as e:
            errors.append(f"{cid}: {e}")
    return errors


# ---------------------------------------------------------------- G6: one row

def validate_row(case_id: str, status: str, steps, audit_at: str, evidence_index: dict) -> list[str]:
    e = []
    if status not in STATUSES:
        return [f"{case_id}: bad status {status!r}"]
    if not isinstance(steps, list):
        return [f"{case_id}: steps_json is not a JSON array"]
    if status == "NOT_APPLICABLE":
        return [] if steps == [] else [f"{case_id}: NOT_APPLICABLE must have []"]
    if not steps:
        return [f"{case_id}: {status} needs steps"]

    cutoff = ts(audit_at)
    prev = None
    for i, s in enumerate(steps, 1):
        where = f"{case_id} step {i}"
        if not isinstance(s, dict) or set(s) != STEP_KEYS:
            e.append(f"{where}: keys must be exactly {sorted(STEP_KEYS)}")
            continue
        if s["step_no"] != i or isinstance(s["step_no"], bool):
            e.append(f"{where}: step_no {s['step_no']!r} != {i}")
        op = s["operation"]
        if op not in OP_PHASE:
            e.append(f"{where}: unknown operation {op!r}")
            continue
        if s["phase"] != OP_PHASE[op] or s["state"] != OP_STATE[op]:
            e.append(f"{where}: {op} needs phase {OP_PHASE[op]} state {OP_STATE[op]}")
            continue
        if not (isinstance(s["system_id"], str) and s["system_id"] and isinstance(s["resource_id"], str) and s["resource_id"]):
            e.append(f"{where}: empty system_id/resource_id")
            continue
        key = step_sort_key(s)
        if prev is not None and key <= prev:
            e.append(f"{where}: out of order or duplicate {key}")
        prev = key

        ev = s["evidence_id"]
        future = status == "INCOMPLETE" and s["phase"] != "FINDING"
        if future and ev != "":
            e.append(f"{where}: proposed {s['phase']} step must have empty evidence_id")
        elif not future:
            if not ev:
                e.append(f"{where}: must cite evidence")
            elif ev not in evidence_index:
                e.append(f"{where}: unknown evidence_id {ev!r}")
            elif evidence_index[ev] > cutoff:
                e.append(f"{where}: {ev} is after audit_at")  # G5 re-check

    phases = {s.get("phase") for s in steps if isinstance(s, dict)}
    if status == "COMPLETE" and phases != {"VERIFICATION"}:
        e.append(f"{case_id}: COMPLETE may contain only VERIFICATION steps")
    if status == "INCOMPLETE" and "FINDING" not in phases:
        e.append(f"{case_id}: INCOMPLETE needs at least one FINDING")
    return e


# ---------------------------------------------------------------- G7: whole file

def validate_output(output_path: Path, requests_path: Path, case_ids: set[str] | None = None) -> list[str]:
    """Whole-file check. case_ids restricts the expected case set (partial runs via --cases)."""
    requests = [r for r in load_requests(requests_path) if case_ids is None or r["case_id"] in case_ids]
    try:
        rows = read_csv(output_path, OUTPUT_HEADER)
    except ValueError as err:
        return [str(err)]
    errors = []
    want = [r["case_id"] for r in requests]
    got = [r["case_id"] for r in rows]
    if sorted(got) != sorted(want):
        missing, extra = set(want) - set(got), set(got) - set(want)
        errors.append(f"case set mismatch: {len(missing)} missing, {len(extra)} extra, {len(got) - len(set(got))} duplicated")
    if got != sorted(got, key=case_sort_key):
        errors.append("rows not sorted by numeric case_id")

    audit_at = {r["case_id"]: r["audit_at"] for r in requests}
    index = load_evidence_index()
    for r in rows:
        cid = r["case_id"]
        if cid not in audit_at:
            continue
        try:
            steps = json.loads(r["steps_json"])
        except json.JSONDecodeError as err:
            errors.append(f"{cid}: invalid JSON ({err.msg})")
            continue
        errors += validate_row(cid, r["deletion_status"], steps, audit_at[cid], index)
    return errors


def write_output(rows: list[tuple[str, str, list]], path: Path) -> None:
    """rows = [(case_id, status, steps)]. Deterministic: numeric sort, compact JSON, fixed key order."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(OUTPUT_HEADER)
        for cid, status, steps in sorted(rows, key=lambda r: case_sort_key(r[0])):
            w.writerow([cid, status, json.dumps(steps, separators=(",", ":"), ensure_ascii=False, sort_keys=True)])
