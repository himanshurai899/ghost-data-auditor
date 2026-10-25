"""Ghost Data deletion auditor — CLI (grading entry point).

    python code/main.py                                   # all 518 cases -> ./output.csv
    python code/main.py --requests dataset/sample_deletion_requests.csv --out runs/sample_pred.csv
    python code/main.py --cases case_33 case_34           # partial run
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghost import llm  # noqa: E402
from ghost.contract import DATASET, REPO  # noqa: E402
from ghost.pipeline import GateFailure, run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit deletion requests and write output.csv")
    ap.add_argument("--requests", type=Path, default=DATASET / "deletion_requests.csv")
    ap.add_argument("--out", type=Path, default=REPO / "output.csv")
    ap.add_argument("--cases", nargs="*", help="only these case ids")
    ap.add_argument("--online", action="store_true", help="allow LLM calls (needs NVIDIA_API_KEY); default is offline")
    ap.add_argument("--strict-temporal", action="store_true",
                    help="discover resources only from evidence captured at or before audit_at (default also allows later files)")
    a = ap.parse_args()
    llm.load_env()  # gitignored .env; real environment variables take precedence
    try:
        m = run(a.requests, a.out, cases=a.cases, offline=not a.online, strict_temporal=a.strict_temporal)
    except GateFailure as e:
        print(f"GATE FAILURE {e}", file=sys.stderr)
        return 2
    print(f"run {m['run_id']}: {m['cases']} cases -> {a.out} (sha256 {m['output_sha256'][:12]}…)")
    print(f"trail: runs/{m['run_id']}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
