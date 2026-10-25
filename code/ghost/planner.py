"""S7 Plan: ResourceVerdicts -> (status, ordered steps). Ordering via contract.finalize_steps."""
from .contract import OP_PHASE, OP_STATE, finalize_steps

# required_state -> (remediation op, verification op)
_REMEDIATE = {"ABSENT": "DELETE_RECORD", "REDACTED": "REDACT_RECORD", "ANONYMIZED": "ANONYMIZE_RECORD",
              "DISABLED": "DISABLE_DATA_FLOW", "BLOCKED": "BLOCK_RESTORE"}
_VERIFY = {"ABSENT": "VERIFY_RECORD_ABSENT", "PRESENT": "VERIFY_RECORD_PRESENT", "REDACTED": "VERIFY_RECORD_REDACTED",
           "ANONYMIZED": "VERIFY_RECORD_ANONYMIZED", "DISABLED": "VERIFY_DATA_FLOW_DISABLED",
           "BLOCKED": "VERIFY_RESTORE_BLOCKED"}


def _finding_op(v) -> str | None:
    if v.kind == "FLOW":
        return "REPORT_ACTIVE_DATA_FLOW"
    if v.kind == "RESTORE":
        return "REPORT_RESTORE_RISK"
    if v.required_state == "ABSENT":
        return "REPORT_REMAINING_RECORD"
    if v.required_state in ("REDACTED", "ANONYMIZED"):
        return "REPORT_EXPOSED_PII"
    return None  # PRESENT-required record that went missing: no finding operation exists


def _step(v, op: str, evidence_id: str) -> dict:
    return {"step_no": 0, "phase": OP_PHASE[op], "system_id": v.system_id, "resource_id": v.resource_id,
            "operation": op, "state": OP_STATE[op], "evidence_id": evidence_id}


def plan(verdicts) -> tuple[str, list[dict]]:
    """COMPLETE: evidence-cited verification only. INCOMPLETE: findings + remediation + verification of every resource."""
    verdicts = list(verdicts)
    if not verdicts:
        raise ValueError("planner: no verdicts")
    bad = [v for v in verdicts if not v.compliant]
    steps = []
    if not bad:
        steps = [_step(v, _VERIFY[v.required_state], v.evidence_id) for v in verdicts]
        status = "COMPLETE"
    else:
        for v in bad:
            f = _finding_op(v)
            if f:
                steps.append(_step(v, f, v.evidence_id))
            if v.required_state in _REMEDIATE:
                steps.append(_step(v, _REMEDIATE[v.required_state], ""))
        if not any(s["phase"] == "FINDING" for s in steps):
            raise ValueError("planner: non-compliant verdicts yield no finding")
        steps += [_step(v, _VERIFY[v.required_state], "") for v in verdicts]
        status = "INCOMPLETE"
    seen, uniq = set(), []
    for s in steps:  # validate_row rejects duplicate (phase, op, system, resource)
        k = (s["operation"], s["system_id"], s["resource_id"])
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return status, finalize_steps(uniq)
