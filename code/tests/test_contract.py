import json

from ghost import contract as c

AUDIT_AT = "2026-09-03T11:30:00Z"


def step(op, system="account_service", resource="account_001", evidence=""):
    return {"step_no": 0, "phase": c.OP_PHASE[op], "system_id": system, "resource_id": resource,
            "operation": op, "state": c.OP_STATE[op], "evidence_id": evidence}


def numbered(steps):
    return [{**s, "step_no": i} for i, s in enumerate(steps, 1)]


INDEX = {"evidence_54": c.ts("2026-09-01T00:00:00Z"), "evidence_99": c.ts("2026-12-01T00:00:00Z")}


def errors(status, steps):
    return c.validate_row("case_01", status, steps, AUDIT_AT, INDEX)


def test_gold_samples_pass_validator():
    assert c.validate_output(c.DATASET / "sample_output.csv", c.DATASET / "sample_deletion_requests.csv") == []


def test_case_sort_is_numeric():
    assert sorted(["case_100", "case_33", "case_5"], key=c.case_sort_key) == ["case_5", "case_33", "case_100"]


def test_not_applicable_requires_empty_steps():
    assert errors("NOT_APPLICABLE", []) == []
    assert errors("NOT_APPLICABLE", numbered([step("VERIFY_RECORD_ABSENT", evidence="evidence_54")]))


def test_complete_is_verification_only_and_cited():
    ok = numbered([step("VERIFY_RECORD_ABSENT", evidence="evidence_54")])
    assert errors("COMPLETE", ok) == []
    assert errors("COMPLETE", numbered([step("VERIFY_RECORD_ABSENT")]))  # uncited
    assert errors("COMPLETE", numbered([step("DELETE_RECORD", evidence="evidence_54")]))


def test_incomplete_future_steps_have_empty_evidence():
    good = numbered([step("REPORT_REMAINING_RECORD", evidence="evidence_54"), step("DELETE_RECORD"),
                     step("VERIFY_RECORD_ABSENT")])
    assert errors("INCOMPLETE", good) == []
    bad = numbered([step("REPORT_REMAINING_RECORD", evidence="evidence_54"), step("DELETE_RECORD", evidence="evidence_54")])
    assert any("empty evidence_id" in e for e in errors("INCOMPLETE", bad))


def test_evidence_after_audit_at_rejected():
    assert any("after audit_at" in e for e in errors("COMPLETE", numbered([step("VERIFY_RECORD_ABSENT", evidence="evidence_99")])))


def test_unknown_evidence_rejected():
    assert any("unknown evidence_id" in e for e in errors("COMPLETE", numbered([step("VERIFY_RECORD_ABSENT", evidence="nope")])))


def test_order_enforced_operation_then_system_then_resource():
    out_of_order = numbered([step("VERIFY_RECORD_PRESENT", "security_service", evidence="evidence_54"),
                             step("VERIFY_RECORD_ABSENT", evidence="evidence_54")])
    assert any("out of order" in e for e in errors("COMPLETE", out_of_order))


def test_phase_state_mismatch_and_bad_numbering():
    s = step("VERIFY_RECORD_ABSENT", evidence="evidence_54")
    assert errors("COMPLETE", [{**s, "step_no": 1, "state": "PRESENT"}])
    assert errors("COMPLETE", [{**s, "step_no": 2}])
    assert errors("COMPLETE", [{**s, "step_no": True}])


def test_extra_keys_rejected():
    assert errors("COMPLETE", [{**step("VERIFY_RECORD_ABSENT", evidence="evidence_54"), "step_no": 1, "note": "x"}])


def test_finalize_steps_sorts_and_numbers():
    steps = c.finalize_steps([step("VERIFY_RECORD_ABSENT", "search_service"), step("DELETE_RECORD"),
                              step("REPORT_REMAINING_RECORD", evidence="evidence_54")])
    assert [s["operation"] for s in steps] == ["REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"]
    assert [s["step_no"] for s in steps] == [1, 2, 3]


def test_write_output_is_sorted_and_compact(tmp_path):
    out = tmp_path / "o.csv"
    c.write_output([("case_10", "NOT_APPLICABLE", []), ("case_9", "NOT_APPLICABLE", [])], out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines == ["case_id,deletion_status,steps_json", "case_9,NOT_APPLICABLE,[]", "case_10,NOT_APPLICABLE,[]"]


def test_check_inputs_flags_duplicates_and_bad_status():
    r = {"case_id": "case_1", "requested_at": "2026-01-02T00:00:00Z", "audit_at": "2026-01-03T00:00:00Z",
         "reported_status": "COMPLETE"}
    assert c.check_inputs([r]) == []
    assert c.check_inputs([r, r])
    assert c.check_inputs([{**r, "reported_status": "DONE"}])


def test_real_requests_pass_g1():
    assert c.check_inputs(c.load_requests(c.DATASET / "deletion_requests.csv")) == []


def test_steps_json_roundtrip_is_valid_json(tmp_path):
    out = tmp_path / "o.csv"
    s = numbered([step("VERIFY_RECORD_ABSENT", evidence="evidence_54")])
    c.write_output([("case_1", "COMPLETE", s)], out)
    row = c.read_csv(out, c.OUTPUT_HEADER)[0]
    assert json.loads(row["steps_json"]) == s


def test_validate_output_can_restrict_to_case_subset(tmp_path):
    out = tmp_path / "o.csv"
    c.write_output([("case_01", "NOT_APPLICABLE", [])], out)
    req = c.DATASET / "sample_deletion_requests.csv"
    assert any("case set mismatch" in e for e in c.validate_output(out, req))
    assert c.validate_output(out, req, case_ids={"case_01"}) == []
