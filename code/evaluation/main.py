"""Scorer: compare predicted output.csv with a gold file (sample_output.csv or custom expected.csv).

Only code/evaluation may read gold answers (threat T8). Usage:
    python code/evaluation/main.py --pred runs/sample_pred.csv [--gold dataset/sample_output.csv] [--json]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ghost.contract import DATASET, OUTPUT_HEADER, case_sort_key, read_csv  # noqa: E402

FIELDS = ("phase", "system_id", "resource_id", "operation", "state", "evidence_id")


def load(path: Path) -> dict[str, tuple[str, list]]:
    return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in read_csv(path, OUTPUT_HEADER)}


def score(pred: dict, gold: dict) -> dict:
    status_ok = seq_ok = tp = n_pred = n_gold = field_hits = field_total = 0
    diffs = []
    for cid in sorted(gold, key=case_sort_key):
        g_status, g_steps = gold[cid]
        p_status, p_steps = pred.get(cid, (None, []))
        status_ok += p_status == g_status
        seq_ok += p_status == g_status and p_steps == g_steps

        g_set = Counter(tuple(st[f] for f in FIELDS) for st in g_steps)
        p_set = Counter(tuple(st.get(f) for f in FIELDS) for st in p_steps)
        tp += sum((g_set & p_set).values())
        n_pred += len(p_steps)
        n_gold += len(g_steps)

        for i in range(max(len(g_steps), len(p_steps))):
            gs = g_steps[i] if i < len(g_steps) else {}
            ps = p_steps[i] if i < len(p_steps) else {}
            field_hits += sum(gs.get(f) == ps.get(f) and f in gs for f in FIELDS)
            field_total += len(FIELDS)

        if p_status != g_status or p_steps != g_steps:
            first = next((i for i in range(max(len(g_steps), len(p_steps)))
                          if i >= len(g_steps) or i >= len(p_steps) or g_steps[i] != p_steps[i]), None)
            diffs.append({"case_id": cid, "gold_status": g_status, "pred_status": p_status,
                          "missing": sorted(set(g_set) - set(p_set)), "extra": sorted(set(p_set) - set(g_set)),
                          "first_diff_index": first})

    n = len(gold) or 1
    precision = tp / n_pred if n_pred else (1.0 if not n_gold else 0.0)
    recall = tp / n_gold if n_gold else 1.0
    return {
        "cases": len(gold),
        "status_accuracy": status_ok / n,
        "step_precision": precision,
        "step_recall": recall,
        "step_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "field_accuracy": field_hits / field_total if field_total else 1.0,
        "sequence_accuracy": seq_ok / n,
        "diffs": diffs,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pred", type=Path, required=True)
    ap.add_argument("--gold", type=Path, default=DATASET / "sample_output.csv")
    ap.add_argument("--json", action="store_true", help="print metrics as JSON (used by scripts/gate.py)")
    ap.add_argument("--diffs", type=int, default=10, help="how many failing cases to print")
    a = ap.parse_args()
    m = score(load(a.pred), load(a.gold))
    if a.json:
        print(json.dumps({k: v for k, v in m.items() if k != "diffs"} | {"failing": len(m["diffs"])}))
        return 0
    print("| Metric | Value |\n|---|---|")
    for k in ("cases", "status_accuracy", "step_precision", "step_recall", "step_f1", "field_accuracy", "sequence_accuracy"):
        print(f"| {k} | {m[k]:.3f} |" if isinstance(m[k], float) else f"| {k} | {m[k]} |")
    for d in m["diffs"][: a.diffs]:
        print(f"\n{d['case_id']}: gold={d['gold_status']} pred={d['pred_status']} first_diff_at={d['first_diff_index']}")
        for t in d["missing"]:
            print("  - missing", t)
        for t in d["extra"]:
            print("  + extra  ", t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
