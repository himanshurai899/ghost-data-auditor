from evaluation.main import load, score
from ghost import contract as c


def s(n, op, res, ev=""):
    return {"step_no": n, "phase": c.OP_PHASE[op], "system_id": "account_service", "resource_id": res,
            "operation": op, "state": c.OP_STATE[op], "evidence_id": ev}


GOLD = {
    "case_1": ("INCOMPLETE", [s(1, "REPORT_REMAINING_RECORD", "a1", "evidence_1"), s(2, "DELETE_RECORD", "a1"),
                              s(3, "VERIFY_RECORD_ABSENT", "a1")]),
    "case_2": ("NOT_APPLICABLE", []),
}


def test_perfect_prediction_scores_one():
    m = score(GOLD, GOLD)
    assert (m["status_accuracy"], m["step_f1"], m["field_accuracy"], m["sequence_accuracy"]) == (1, 1, 1, 1)
    assert m["diffs"] == []


def test_missing_case_counts_as_wrong():
    m = score({"case_1": GOLD["case_1"]}, GOLD)
    assert m["status_accuracy"] == 0.5 and m["sequence_accuracy"] == 0.5


def test_reordered_steps_keep_f1_but_lose_sequence():
    g = GOLD["case_1"][1]
    pred = {**GOLD, "case_1": ("INCOMPLETE", [g[1], g[0], g[2]])}
    m = score(pred, GOLD)
    assert m["step_f1"] == 1 and m["sequence_accuracy"] == 0.5 and m["field_accuracy"] < 1


def test_wrong_evidence_lowers_step_f1():
    g = GOLD["case_1"][1]
    pred = {**GOLD, "case_1": ("INCOMPLETE", [{**g[0], "evidence_id": "evidence_2"}, g[1], g[2]])}
    m = score(pred, GOLD)
    assert m["status_accuracy"] == 1 and m["step_f1"] < 1
    assert m["diffs"][0]["case_id"] == "case_1"


def test_gold_file_scores_perfect_against_itself():
    gold = load(c.DATASET / "sample_output.csv")
    assert len(gold) == 32 and score(gold, gold)["sequence_accuracy"] == 1
