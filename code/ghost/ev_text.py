"""Logs (26) and TXT ledger (1): docs/evidence_field_map.md §2.3, §2.4, §2.5. Join started/completed lines on trace id.

One pass turns every line into (timestamp, fields) whatever its envelope (kv, JSON, syslog, bracket, pipe, cloud).
Subject keys live on `*_started` lines, so they are collected per trace id and attached to the state line of the same
trace. Only lines that carry a `resource_id` and a known state event become Facts. Logs and ledgers never prove
absence by omission, so coverage is always empty.
"""
import json
import re
from pathlib import Path

MAX_LINE = 8192  # logs are untrusted: bound every regex scan (the kv scan is O(n) per start position)
TS = re.compile(r"\d{4}-\d\d-\d\dT[\d:.]+Z?")
KV = re.compile(r'([A-Za-z_][\w.]*)=("(?:[^"\\]|\\.)*"|\S*)')
BRACKET = re.compile(r"\[(\w+)\] \[([^\]]*)\] \[([^\]]*)\] (\w+):? ?(.*)", re.S)
SYSLOG = re.compile(r"<\d+>1 (\S+) (\S+) (\S+) - - (.*)", re.S)
PIPE_HEAD = re.compile(r"\| [A-Za-z]+ \| ")
KV_HEAD = re.compile(r"(?:[A-Z]+ )?[A-Za-z_]\w*=")
EMAIL = re.compile(r"[^@\s\"]+@[^@\s\"]+")
HASH = re.compile(r"[0-9a-fA-F]{64}")
USER = re.compile(r"user_\d+")
PHONE = re.compile(r"\+?[\d\s().-]{7,}")
# fields that can carry a subject identifier (started lines: lookup/match/subject/scan/owner keys)
KEY_FIELDS = ("lookup_key", "match_key", "subject_key", "scan_key", "subject_ref", "owner_key", "correlation_key",
              "subject_reference", "matched_value", "email", "customer_email", "owner_email", "requester_email",
              "phone", "requester_phone", "email_hash", "customer_reference", "user_id")
PII_CATEGORIES = {"SUPPORT_MESSAGE", "SUPPORT_ATTACHMENT", "ANALYTICS_PROFILE", "ACCOUNT_TOMBSTONE"}
TRUE, FALSE = {"true", "1", "yes"}, {"false", "0", "no"}
LEDGER_RESULT = {"FOUND": "PRESENT", "IDENTIFIABLE": "PRESENT", "NOT_FOUND": "ABSENT", "ANONYMIZED": "ANONYMIZED",
                 "REDACTED": "REDACTED", "DISABLED": "FLOW_DISABLED", "BLOCKED": "RESTORE_BLOCKED"}
TXT_ROW = re.compile(r"- (\d{4}-\d\d-\d\dT[\d:.]+Z?) \| (.*)")
STATE_EVENTS = {
    "profile_lookup_completed", "index_query_completed", "support_ticket_read_completed", "message_pii_scan",
    "attachment_pii_scan", "message_read", "analytics_profile_read", "analytics_profile_read_completed",
    "analytics_identity_scan", "contact_lookup_completed", "contact_query_completed", "deletion_marker_check",
    "connector_config_read_completed", "connector_heartbeat", "connector_config_loaded", "restore_policy_read_completed",
    "restore_candidate_evaluated", "restore_authorization_completed", "audit_record_read_completed",
    "export_metadata_read_completed", "export_download_check_completed", "retained_order_loaded", "record_lookup",
}


def _kv(s: str) -> dict:
    d = {}
    for k, v in KV.findall(s):
        d[k] = v[1:-1].replace('\\"', '"') if len(v) >= 2 and v[0] == '"' and v[-1] == '"' else v
    return d


def _line(raw: str):
    """-> (ts, fields) for any of the six envelopes; ValueError when the line fits none."""
    raw = raw[:MAX_LINE]
    ts, _, rest = raw.partition(" ")
    if not TS.fullmatch(ts):
        raise ValueError(f"no timestamp: {raw[:60]!r}")
    if rest.startswith("{"):
        obj = json.loads(rest)
        if not isinstance(obj, dict):
            raise ValueError("JSON envelope is not an object")
        return ts, {k: "null" if v is None else str(v) for k, v in obj.items()}
    if rest.startswith("["):
        m = BRACKET.fullmatch(rest)
        if not m:
            raise ValueError(f"bad bracket envelope: {raw[:80]!r}")
        d = _kv(m.group(5))
        d.update(level=m.group(1), service=m.group(2), trace_id=m.group(3), event=m.group(4))
        return ts, d
    if rest.startswith("<"):
        m = SYSLOG.fullmatch(rest)
        if not m:
            raise ValueError(f"bad syslog envelope: {raw[:80]!r}")
        d = _kv(m.group(4))
        d.update(service=m.group(2), trace_id=m.group(3))
        return ts, d
    if PIPE_HEAD.match(rest):
        p = rest.removeprefix("| ").split(" | ", 4)
        d = _kv(p[4]) if len(p) > 4 else {}
        if len(p) > 3:
            d.update(level=p[0], service=p[1], trace_id=p[2], event=p[3])
        return ts, d
    if rest.startswith("requestId="):
        o = _kv(rest)
        d = _kv(o.get("message", ""))
        d.update(trace_id=o["requestId"], service=o.get("function", ""))
        return ts, d
    if KV_HEAD.match(rest):
        return ts, _kv(rest)
    raise ValueError(f"unrecognised log envelope: {raw[:80]!r}")


def _classify(v: str) -> tuple[str, str] | None:
    from .evidence import is_null
    if is_null(v):
        return None
    v = v.strip()
    if EMAIL.fullmatch(v):
        return "email", v
    if USER.fullmatch(v):
        return "user_id", v
    if HASH.fullmatch(v):
        return "email_hash", v
    if PHONE.fullmatch(v):
        return "phone", v
    return None


def _keys(d: dict) -> dict:
    out = {}
    for f in KEY_FIELDS:
        c = _classify(d.get(f, "null"))
        if c:
            out.setdefault(c[0], c[1])
    return out


def _flag(v):
    v = str(v).strip().lower()
    return True if v in TRUE else False if v in FALSE else None


def _state(ev: str, d: dict):
    """-> (category, observation) | None for a state-bearing event (field map §1.4, §1.5)."""
    from .evidence import is_null
    if ev == "profile_lookup_completed":
        r, h = d.get("rows"), d.get("http_status")
        obs = "PRESENT" if r == "1" or h == "200" else "ABSENT" if r == "0" or h == "404" else None
        return ("USER_PROFILE", obs) if obs else None
    if ev == "index_query_completed":
        r, n = d.get("result"), d.get("total_hits")
        obs = "PRESENT" if r == "hit" or (n or "0").isdigit() and int(n or 0) >= 1 else "ABSENT" if r == "miss" or n == "0" else None
        return ("SEARCH_INDEX_ENTRY", obs) if obs else None
    if ev == "support_ticket_read_completed":
        exposed = any(not is_null(d.get(k)) for k in ("requester_name", "requester_email", "requester_phone"))
        return "SUPPORT_MESSAGE", "PRESENT" if exposed else "REDACTED"
    if ev == "message_pii_scan":
        return "SUPPORT_MESSAGE", "PRESENT"
    if ev == "attachment_pii_scan":
        return "SUPPORT_ATTACHMENT", "PRESENT"
    if ev == "message_read":
        return "SUPPORT_MESSAGE", "REDACTED" if d.get("message_text", "").strip().upper() == "[REDACTED]" else "PRESENT"
    if ev == "analytics_identity_scan":
        return "ANALYTICS_PROFILE", "PRESENT"
    if ev in ("analytics_profile_read", "analytics_profile_read_completed"):
        di = d.get("direct_identifiers")
        if di is not None:
            return "ANALYTICS_PROFILE", "ANONYMIZED" if di.strip() == "0" else "PRESENT"
        populated = any(not is_null(d.get(k)) for k in ("customer_reference", "user_id", "email", "phone", "email_hash"))
        return "ANALYTICS_PROFILE", "PRESENT" if populated else "ANONYMIZED"
    if ev in ("contact_lookup_completed", "contact_query_completed", "deletion_marker_check"):
        # open question (field map §8.2): no rule category is stated; DELETE-always MARKETING_PROFILE matches the samples' op
        return "MARKETING_PROFILE", "ABSENT" if d.get("rows") == "0" else "PRESENT"
    if ev in ("connector_config_read_completed", "connector_heartbeat", "connector_config_loaded"):
        e = _flag(d.get("enabled", ""))
        if e is None:
            e = {"delivered": True, "stopped": False}.get(d.get("last_delivery_status"))
        return ("DATA_FLOW", "FLOW_ACTIVE" if e else "FLOW_DISABLED") if e is not None else None
    if ev == "restore_policy_read_completed":
        a = _flag(d.get("restore_allowed", ""))
        return ("BACKUP_ARCHIVE", "RESTORE_OPEN" if a else "RESTORE_BLOCKED") if a is not None else None
    if ev == "restore_candidate_evaluated":
        open_ = _flag(d.get("eligible", "")) is True and _flag(d.get("deletion_block", "")) is False
        return "BACKUP_ARCHIVE", "RESTORE_OPEN" if open_ else "RESTORE_BLOCKED"
    if ev == "restore_authorization_completed":
        dec = d.get("decision", "").lower()
        return ("BACKUP_ARCHIVE", "RESTORE_BLOCKED" if dec == "deny" else "RESTORE_OPEN") if dec else None
    if ev == "audit_record_read_completed":
        obs = {"1": "PRESENT", "0": "ABSENT"}.get(d.get("rows", "").strip())
        return ("SECURITY_AUDIT_LOG", obs) if obs else None
    if ev in ("export_metadata_read_completed", "export_download_check_completed"):
        a = _flag(d.get("available", ""))
        return ("USER_EXPORT", "PRESENT" if a else "ABSENT") if a is not None else None
    if ev == "retained_order_loaded":
        return "LEGAL_HOLD_RECORD", "PRESENT"
    return None


def _pii(category: str, d: dict) -> frozenset:
    if category not in PII_CATEGORIES:
        return frozenset()
    from .evidence import is_null
    out = {c[0] for f in KEY_FIELDS if (c := _classify(d.get(f, "null"))) and c[0] != "user_id"}
    if category == "ANALYTICS_PROFILE" and any(not is_null(d.get(k)) for k in ("user_id", "customer_reference")):
        out.add("user_id")
    if any(not is_null(d.get(k)) for k in ("requester_name", "name")):
        out.add("name")
    return frozenset(out)


def _ledger_obs(rtype: str, result: str) -> str:
    if result == "ACTIVE":
        return "RESTORE_OPEN" if rtype == "BACKUP_ARCHIVE" else "FLOW_ACTIVE"
    if result not in LEDGER_RESULT:
        raise ValueError(f"unknown ledger result {result!r}")
    return LEDGER_RESULT[result]


def parse(path: Path, meta: dict) -> tuple[list, list]:
    """-> (facts: list[evidence.Fact], coverage: list[evidence.Coverage]). Raise on malformed input."""
    from .evidence import Fact, norm_keys, system_for

    def fact(ts, system, rid, cat, obs, keys, pii):
        sid = system_for(rid, system)
        if sid is None:
            return None
        return Fact(evidence_id=meta["file_id"], evidence_kind="FILE", captured_at=meta["captured_at"], observed_at=ts,
                    system_id=sid, resource_id=rid, category=cat, observation=obs,
                    subject_keys=norm_keys(keys), pii_fields=pii)

    def ledger(ts, system, rid, rtype, result, key):
        k = _classify(key) if key else None
        obs = _ledger_obs(rtype, result)
        pii = frozenset({k[0]} if k and k[0] != "user_id" else {"direct_identifier"}) if result == "IDENTIFIABLE" else frozenset()
        return fact(ts, system, rid, rtype, obs, {k[0]: k[1]} if k else {}, pii)

    facts = []
    lines = [ln.rstrip("\r\n") for ln in Path(path).read_text(encoding="utf-8").splitlines()]
    if Path(path).suffix.lower() == ".txt":
        for ln in lines:
            m = TXT_ROW.fullmatch(ln.strip()[:MAX_LINE])
            if not m:
                if ln.lstrip().startswith("- ") and " | " in ln:
                    raise ValueError(f"malformed ledger row: {ln[:80]!r}")
                continue
            p = [x.strip() for x in m.group(2).split(" | ")]
            if len(p) != 5:
                raise ValueError(f"ledger row needs 6 fields: {ln[:80]!r}")
            facts.append(ledger(m.group(1), p[0], p[1], p[2], p[3], p[4]))
    else:
        recs = [_line(ln) for ln in lines if ln.strip()]
        trace_keys: dict[str, dict] = {}
        for _, d in recs:
            if d.get("trace_id"):
                for k, v in _keys(d).items():
                    trace_keys.setdefault(d["trace_id"], {}).setdefault(k, v)
        for ts, d in recs:
            ev, rid = d.get("event", ""), d.get("resource_id", "")
            if ev not in STATE_EVENTS or not rid:
                continue
            if ev == "record_lookup":
                f = ledger(ts, d.get("system"), rid, d.get("record_type", ""), d.get("result", ""), d.get("subject_reference"))
            else:
                st = _state(ev, d)
                if not st:
                    continue
                f = fact(ts, None, rid, st[0], st[1], {**trace_keys.get(d.get("trace_id"), {}), **_keys(d)}, _pii(st[0], d))
            if f:
                facts.append(f)
    facts.sort(key=lambda f: (f.evidence_id, f.system_id, f.resource_id, f.observation, f.observed_at))
    return facts, []
