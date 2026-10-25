"""PNG screenshots (11) and PDF documents (4): docs/evidence_field_map.md §2.6.

PNG -> Nemotron Parse Markdown (llm.Client.parse_page) -> tokens stripped, LaTeX tables and key/value lines read
deterministically. PDF -> pypdf text layer (a PDF without one is a gap: no facts). Every file's Facts are cached as
code/data/pages/<file_id>.json so the grader and offline runs need neither keys nor network. Committed JSON holds no
dataset emails: each email is stored as its sha256 under `email_hash` (identity.py links on hashes, F-003).

    python code/ghost/ev_page.py --refresh      # needs NVIDIA keys in .env; rewrites the cache
"""
import hashlib
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "data" / "pages"
MAX_PDF_PAGES = 50  # T6: evidence PDFs are 1-2 pages
_FILE_ID = re.compile(r"[A-Za-z0-9_-]+")
_client = None  # set via configure(); None means offline, so a cache miss raises

RES = re.compile(r"\b(?:account|search|support|analytics|export|marketing|backup|data_flow|audit_record|tombstone|legal_hold|object)_\d+\b")
EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
USER = re.compile(r"\buser_\d+\b")
PHONE = re.compile(r"\+\d[\d ()-]{7,}\d")
HASH = re.compile(r"\b[0-9a-fA-F]{64}\b")
TOKENS = re.compile(r"<x_[\d.]+><y_[\d.]+>(?:<class_[\w-]+>)?")
LINK = re.compile(r"(?:linked|confirmed) (\S+) \((.+?)\) (?:to|belongs)")
# REDACT/ANONYMIZE categories: populated direct identifiers on the record are exposed PII (field map §1.4)
PII_CATEGORIES = {"SUPPORT_MESSAGE": ("user_id",), "ANALYTICS_PROFILE": (), "ACCOUNT_TOMBSTONE": ("user_id",)}


def configure(client) -> None:
    global _client
    _client = client


def _clean(md: str) -> str:
    md = TOKENS.sub("", md)
    md = re.sub(r"\\thead\{([^}]*)\}", r"\1", md)
    return md.replace("\\_", "_").replace("\\&", "&").replace("\\%", "%").replace("**", "")


def _split(text: str) -> tuple[list[str], list[str]]:
    """-> (table row texts, plain lines)."""
    rows, plain, in_table = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("\\begin{tabular}"):
            in_table, s = True, s.split("}", 2)[-1].strip() if s.count("}") > 1 else ""
        if s.startswith("\\end{tabular}"):
            in_table = False
            continue
        if in_table:
            s = s.removesuffix("\\\\").replace("&", " | ").strip()
            if s:
                rows.append(s)
        elif s:
            plain.append(s)
    return rows, plain


def _first(rx, text):
    m = rx.search(text)
    return m.group(0) if m else None


def extract(md: str, meta: dict, aliases: dict, pdf: bool) -> list:
    """Page text -> sorted Facts. `aliases`: alias -> resource_id, for pages that never print the resource id."""
    from .evidence import Fact, norm_keys, system_for
    from .activity import PREFIX_CATEGORY
    text = _clean(md)
    rows, plain = _split(text)
    plain_text = "\n".join(plain)
    rid_rows = {}                       # resource id -> its table rows
    for r in rows:
        for rid in RES.findall(r):
            rid_rows.setdefault(rid, []).append(r)
    plain_ids = [i for i in dict.fromkeys(RES.findall(plain_text)) if i not in rid_rows]
    primary = list(rid_rows) or plain_ids[:1]  # activity feeds also mention neighbours' ids: only the table or the subject counts
    for alias, rid in aliases.items():
        lines = [ln for ln in text.splitlines() if alias.lower() in ln.lower()]
        whole = any(ln.strip().lower() == alias.lower() for ln in lines)
        if rid not in primary and (whole if USER.fullmatch(alias) else lines):
            primary.append(rid)
    facts = set()
    for rid in primary:
        scope = "\n".join(rid_rows[rid]) if rid in rid_rows else plain_text
        emails = sorted({e.lower() for e in EMAIL.findall(scope)}) or [None]
        cat = PREFIX_CATEGORY.get(next((p for p in PREFIX_CATEGORY if rid.startswith(p)), ""), "")
        if rid.startswith("object_") or (pdf and rid.startswith("support_")):
            cat = "SUPPORT_ATTACHMENT"
        low = scope.lower() if rid in rid_rows else text.lower()
        if cat == "DATA_FLOW":
            obs = "FLOW_DISABLED" if re.search(r"disabled|paused|stopped|inactive", low) else "FLOW_ACTIVE"
        elif cat == "BACKUP_ARCHIVE":
            obs = ("RESTORE_BLOCKED" if re.search(r"restore (?:blocked|denied)|blocked", low)
                   else "RESTORE_OPEN" if re.search(r"restore (?:allowed|enabled|eligible|available)", low) else "PRESENT")
        else:
            obs = "PRESENT"
        for email in emails:
            raw = {"email_hash": hashlib.sha256(email.encode()).hexdigest() if email else _first(HASH, scope),
                   "phone": _first(PHONE, scope), "user_id": _first(USER, scope)}
            keys = norm_keys(raw)
            pii = frozenset()
            if cat in PII_CATEGORIES:
                pii = frozenset({"email" if k == "email_hash" and email else k for k, _ in keys} - set(PII_CATEGORIES[cat]))
            fobs = obs
            if cat == "ACCOUNT_TOMBSTONE" and not pii:
                fobs = "REDACTED"
            facts.add(Fact(meta["file_id"], "FILE", meta["captured_at"], meta["captured_at"], system_for(rid) or "", rid,
                           cat, fobs, keys, pii))
    return sorted(facts, key=lambda f: (f.resource_id, f.subject_keys))


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader  # lazy: only PDF cache misses and --refresh need it
    pages = PdfReader(str(path)).pages
    return "\n".join((p.extract_text() or "") for p in pages[:MAX_PDF_PAGES]).strip()


def _dump(facts) -> str:
    rows = [dict(asdict(f), subject_keys=[list(k) for k in f.subject_keys], pii_fields=sorted(f.pii_fields)) for f in facts]
    return json.dumps(rows, indent=1, ensure_ascii=True, sort_keys=True) + "\n"


def _load(path: Path) -> list:
    from .evidence import Fact
    return [Fact(**dict(r, subject_keys=tuple(map(tuple, r["subject_keys"])), pii_fields=frozenset(r["pii_fields"])))
            for r in json.loads(path.read_text(encoding="utf-8"))]


def _aliases_from_activity() -> dict:
    from .contract import DATASET, read_csv
    out = {}
    for r in read_csv(DATASET / "system_activity.csv"):
        m = LINK.search(r["details"]) if r["event_type"] == "LINK_RESOURCE_IDENTITY" else None
        if m and m.group(2) != m.group(1):
            out[m.group(2)] = m.group(1)
    return out


def _extract_file(path: Path, meta: dict) -> list:
    if path.suffix.lower() == ".pdf":
        text = _pdf_text(path)
        return extract(text, meta, _aliases_from_activity(), True) if text else []  # no text layer: gap, no facts
    if _client is None:
        raise RuntimeError(f"{meta['file_id']}: no cached page facts in {CACHE} and no online client")
    return extract(_client.parse_page(path.read_bytes()), meta, _aliases_from_activity(), False)


def parse(path, meta: dict) -> tuple[list, list]:
    if not _FILE_ID.fullmatch(meta["file_id"]):  # file_id names a cache file: no separators, no ".."
        raise ValueError(f"unsafe file_id {meta['file_id'][:40]!r}")
    cached = CACHE / f"{meta['file_id']}.json"
    if cached.is_file():
        return _load(cached), []
    return _extract_file(Path(path), meta), []


def refresh() -> None:
    import time
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ghost import ev_page, llm
    from ghost.contract import DATASET, read_csv
    llm.load_env(Path(sys.argv[sys.argv.index("--env") + 1])) if "--env" in sys.argv else llm.load_env()
    client = llm.Client()
    ev_page.configure(client)
    ledger = Path(__file__).resolve().parents[1] / "data" / "usage_cache_build.jsonl"  # tokens only, no PII
    CACHE.mkdir(parents=True, exist_ok=True)
    for meta in read_csv(DATASET / "evidence_files.csv"):
        path = DATASET / meta["file_path"]
        if path.suffix.lower() not in (".png", ".pdf"):
            continue
        mark = len(client.usage)
        for attempt in range(4):
            try:
                facts = ev_page._extract_file(path, meta)
                break
            except (OSError, llm.LLMError) as e:  # llm.urllib_transport lets raw socket resets through
                print(f"{meta['file_id']}: retry after {type(e).__name__}", file=sys.stderr)
                time.sleep(5)
        else:
            raise RuntimeError(f"{meta['file_id']}: page extraction kept failing")
        with open(ledger, "a", encoding="utf-8", newline="\n") as f:
            for u in client.usage[mark:]:
                f.write(json.dumps({"file_id": meta["file_id"], "provider": u["provider"], "model": u["model"], "role": u["role"],
                                    "prompt_tokens": u["prompt_tokens"] or None, "output_tokens": u["output_tokens"] or None},
                                   sort_keys=True) + "\n")
        (CACHE / f"{meta['file_id']}.json").write_text(_dump(facts), encoding="utf-8", newline="\n")
        print(meta["file_id"], len(facts))


if __name__ == "__main__":
    if "--refresh" not in sys.argv:
        sys.exit(__doc__)
    refresh()
