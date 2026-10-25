"""S4b: orphan-resource discovery (F-020). Some resources of a subject carry no identifier in any evidence file;
only the deletion worker's batch rows in system_activity.csv mention them. The worker runs once a day, handles
each user's account first, then a per-user chain of other resources spaced by a fixed gap (7 or 19 minutes).
These regularities are measured from the cases that DO link by text (no labels), then used to place the
unlinked rows. Every rule only adds a resource that no other subject owns, and only from rows at or before
audit_at. Rules (precision/recall in the PR description):

  R1 id alignment : user_N and an unowned worker DELETE of account_NNN inside [requested_at, audit_at].
  R2 account batch: the account row is on the day of the subject's first chain row, before it, with a delay
                    inside the range measured from text-linked subjects; unique candidates are taken first,
                    a remaining two-way tie is broken by the delay closest to the measured median.
  R3 analytics    : an unowned worker ANONYMIZE of an analytics row falling on the subject's chain grid
                    (anchor time + k * gap), when exactly one such row exists.
"""
import collections
import re

from .contract import DATASET, load_requests, read_csv, ts

_ACC, _ANA = "account_", "analytics_"


def _min(t: str) -> int:
    return int(ts(t).timestamp() // 60)


def load_rows(rows=None) -> list:
    """Deletion-worker rows only (sorted by time): the one source that names unlinked resources."""
    rows = read_csv(DATASET / "system_activity.csv") if rows is None else rows
    return sorted((r for r in rows if r["source_system"] == "deletion_worker"), key=lambda r: r["event_time"])


def _anchors(have, by_res, req, aud):
    out = [r for x in have if not x.startswith(_ACC) for r in by_res.get(x, ()) if req <= r["event_time"] <= aud]
    return sorted(out, key=lambda r: r["event_time"])


def _gap(anchors):
    t = [_min(r["event_time"]) for r in anchors if r["event_time"][:10] == anchors[0]["event_time"][:10]]
    g = [b - a for a, b in zip(t, t[1:]) if 0 < b - a < 60]
    return min(g) if g else None


def assign(cases, rows, owned) -> dict:
    """cases: [{id, user_id, req, aud, have:set(resource_id)}]; rows: load_rows(); owned: resources some subject
    already owns by text. Returns {case_id: sorted resource_ids} for resources not in the case's `have`."""
    by_res = collections.defaultdict(list)
    for r in rows:
        by_res[r["resource_id"]].append(r)
    taken = set(owned) | {x for c in cases for x in c["have"]}
    free_acc = [r for r in rows if r["event_type"] == "DELETE_RECORD" and r["resource_id"].startswith(_ACC)
                and r["resource_id"] not in taken]
    free_ana = [r for r in rows if r["event_type"] == "ANONYMIZE_RECORD" and r["resource_id"].startswith(_ANA)
                and r["resource_id"] not in taken]
    out = collections.defaultdict(set)

    def grab(cid, res):
        out[cid].add(res)
        taken.add(res)

    # R1: id alignment
    for c in cases:
        m = re.fullmatch(r"user_(\d+)", c["user_id"])
        if not m or any(x.startswith(_ACC) for x in c["have"]):
            continue
        want = f"{_ACC}{int(m.group(1)):03d}"
        if want not in taken and any(c["req"] <= r["event_time"] <= c["aud"] for r in by_res.get(want, ())
                                     if r["event_type"] == "DELETE_RECORD"):
            grab(c["id"], want)

    # learn account -> first chain row delay per chain gap, from subjects that link by text
    learn = collections.defaultdict(list)
    anc = {c["id"]: _anchors(c["have"], by_res, c["req"], c["aud"]) for c in cases}
    for c in cases:
        a = anc[c["id"]]
        acct = [r for x in c["have"] if x.startswith(_ACC) for r in by_res.get(x, ())
                if r["event_type"] == "DELETE_RECORD" and a and r["event_time"][:10] == a[0]["event_time"][:10]]
        if a and acct:
            learn[_gap(a)].append(_min(a[0]["event_time"]) - _min(acct[0]["event_time"]))
    allv = sorted(v for vs in learn.values() for v in vs)

    def bounds(g):
        v = sorted(learn.get(g, ())) if g is not None and len(learn.get(g, ())) >= 5 else allv
        return (v[0], v[-1], v[len(v) // 2]) if v else None

    # R2: account of the batch
    need = [c for c in cases if anc[c["id"]] and not any(x.startswith(_ACC) for x in c["have"] | out[c["id"]])]
    feas = {}
    for c in need:
        a, b = anc[c["id"]], None
        b = bounds(_gap(a))
        if b is None:
            continue
        t0, day = _min(a[0]["event_time"]), a[0]["event_time"][:10]
        feas[c["id"]] = [(abs((t0 - _min(r["event_time"])) - b[2]), r["resource_id"]) for r in free_acc
                         if r["event_time"][:10] == day and b[0] <= t0 - _min(r["event_time"]) <= b[1]]
    changed = True
    while changed:
        changed = False
        for cid in sorted(feas):
            if cid in out and any(x.startswith(_ACC) for x in out[cid]):
                continue
            opts = sorted((d, x) for d, x in feas[cid] if x not in taken)
            if len(opts) == 1:
                grab(cid, opts[0][1])
                changed = True
    for cid in sorted(feas):  # two-way ties only: p >= 0.5 beats the F1 break-even (~F1/2)
        if any(x.startswith(_ACC) for x in out[cid]):
            continue
        opts = sorted((d, x) for d, x in feas[cid] if x not in taken)
        if len(opts) == 2:
            grab(cid, opts[0][1])

    # R3: analytics on the chain grid
    for c in cases:
        a, cid = anc[c["id"]], c["id"]
        if not a or _gap(a) is None or any(x.startswith(_ANA) for x in c["have"]):
            continue
        g, t0, day = _gap(a), _min(a[0]["event_time"]), a[0]["event_time"][:10]
        hits = [r["resource_id"] for r in free_ana if r["resource_id"] not in taken and r["event_time"][:10] == day
                and (_min(r["event_time"]) - t0) % g == 0 and abs(_min(r["event_time"]) - t0) <= 5 * g]
        if len(hits) == 1:
            grab(cid, hits[0])
    return {k: sorted(v) for k, v in out.items()}


def discover(requests, ctx) -> dict:
    """Run `assign` once per run over every known subject (the requests being audited plus the public sample
    requests, which compete for the same batch rows). Returns {case_id: [(system_id, resource_id)]}."""
    from . import identity, reasoning
    from .evidence import system_for

    known = {r["case_id"]: r for r in requests}
    sample = DATASET / "sample_deletion_requests.csv"
    if sample.exists():
        for r in load_requests(sample):
            known.setdefault(r["case_id"], r)
    cases = []
    for r in known.values():
        sub = identity.resolve(r["email"], r["audit_at"], ctx["identity"])
        if sub is None:
            continue
        lk = reasoning.link(sub, ctx["facts"], r["requested_at"], r["audit_at"], ctx["strict_temporal"])
        cases.append({"id": r["case_id"], "user_id": sub.user_id, "req": r["requested_at"], "aud": r["audit_at"],
                      "have": {x for _, x in lk.resources}})
    owned = {f.resource_id for f in ctx["facts"] if f.subject_keys}
    found = assign(cases, load_rows(), owned)
    return {cid: [(system_for(x) or "", x) for x in xs] for cid, xs in found.items()}


def extend(linked, extra, facts, audit_at: str):
    """Add discovered resources and their citable facts (captured_at <= audit_at) to a `Linked` result."""
    from .reasoning import Linked

    new = frozenset(extra) - linked.resources
    if not new:
        return linked
    aud = ts(audit_at)
    cited = sorted(set(linked.facts) | {f for f in facts if (f.system_id, f.resource_id) in new and ts(f.captured_at) <= aud},
                   key=lambda f: (f.system_id, f.resource_id, ts(f.observed_at), f.evidence_id))
    return Linked(linked.resources | new, tuple(cited), linked.late_only)
