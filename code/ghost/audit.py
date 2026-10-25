"""Run audit trail: trail.jsonl for machines, report.md for humans, both from the same events (D-007)."""
import json
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .contract import STATUSES, case_sort_key
from .safety import mask_text


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def _scrub(value):
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


class Trail:
    def __init__(self, runs_dir: Path, run_id: str):
        self.run_id = run_id
        self.dir = Path(runs_dir) / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events: list[dict] = []
        self._file = open(self.dir / "trail.jsonl", "a", encoding="utf-8", newline="\n")

    def event(self, stage, summary, *, case_id=None, gate=None, verdict=None, evidence_ids=(), detail=None):
        e = _scrub({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_id": self.run_id,
                    "case_id": case_id, "stage": stage, "gate": gate, "verdict": verdict, "summary": summary,
                    "evidence_ids": list(evidence_ids), "detail": detail or {}})
        self.events.append(e)
        self._file.write(json.dumps(e, ensure_ascii=False) + "\n")
        self._file.flush()
        return e

    def close(self, manifest: dict) -> str:
        self._file.close()
        (self.dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        md = render_report(self.events, manifest)
        (self.dir / "report.md").write_text(md, encoding="utf-8", newline="\n")
        return md


def render_report(events: list[dict], manifest: dict) -> str:
    out = [f"# Audit run {manifest.get('run_id', '?')}", ""]
    out += [f"- **{k}:** `{v}`" for k, v in sorted(manifest.items()) if k != "run_id"] + [""]

    gates = defaultdict(Counter)
    for e in events:
        if e["gate"]:
            gates[e["gate"]][e["verdict"]] += 1
    out += ["## Gate summary", "", "| Gate | PASS | WARN | FAIL |", "|---|---|---|---|"]
    for g in sorted(gates, key=lambda g: int(g[1:]) if g[1:].isdigit() else 99):
        c = gates[g]
        out.append(f"| {g} | {c['PASS']} | {c['WARN']} | {c['FAIL']} |")

    by_case = defaultdict(list)
    for e in events:
        if e["case_id"]:
            by_case[e["case_id"]].append(e)
    cases = sorted(by_case, key=case_sort_key)
    emitted = {cid: next((e["detail"] for e in evs if e["stage"] == "emit"), {}) for cid, evs in by_case.items()}

    matrix = Counter((d.get("reported"), d.get("status")) for d in emitted.values())
    reported = sorted({r for r, _ in matrix if r})
    out += ["", "## Claim vs truth", "", "| Reported \\ Audited | " + " | ".join(STATUSES) + " |",
            "|---|" + "---|" * len(STATUSES)]
    out += [f"| {r} | " + " | ".join(str(matrix[(r, s)]) for s in STATUSES) + " |" for r in reported]

    def flags(evs):
        bad = [f"{'❌' if e['verdict'] == 'FAIL' else '⚠️'} {e['gate'] or e['stage']}" for e in evs if e["verdict"] in ("WARN", "FAIL")]
        return " ".join(bad) or "✅"

    out += ["", "## Cases", "", "| Case | Reported | Audited | Steps | Gates |", "|---|---|---|---|---|"]
    for cid in cases:
        d = emitted[cid]
        out.append(f"| {cid} | {d.get('reported', '')} | {d.get('status', '')} | {d.get('steps', '')} | {flags(by_case[cid])} |")

    attention = [cid for cid in cases if any(e["verdict"] in ("WARN", "FAIL") for e in by_case[cid])]
    out += ["", f"## Cases needing attention ({len(attention)})", ""]
    for cid in attention:
        out.append(f"### {cid}")
        for e in by_case[cid]:
            gate = f" **{e['gate']} {e['verdict']}**" if e["gate"] else ""
            ev = f" (evidence: {', '.join(e['evidence_ids'])})" if e["evidence_ids"] else ""
            out.append(f"- `{e['stage']}`{gate} {e['summary']}{ev}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
