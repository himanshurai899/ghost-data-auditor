"""S2 Intent: does request_text authorize deletion? (G3). Untrusted text: treat as data (T2).

Offline rules cover every language in the data (en, es, pt, fr, ja, ko). Order:
1. normalize; drop sentences carrying prompt-injection markers (flagged, never obeyed);
2. remove negated deletion phrases ("don't delete", "not asking for deletion") -> strong NOT_DELETE signal;
3. affirmative deletion vs keep-account / non-deletion asks (access, export, correction, opt-out, login help).
"""
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .contract import DATASET, read_csv

LABELS = ("DELETE", "NOT_DELETE", "UNKNOWN")


@dataclass(frozen=True)
class Intent:
    label: str          # one of LABELS
    confidence: float   # 0..1
    source: str         # rules | llm | adjudicator | stub
    flags: tuple = ()   # e.g. ("injection_marker",)


def _rx(*parts):
    return re.compile("|".join(parts))


def normalize(text: str) -> str:
    """casefold, strip accents from Latin letters only (keeps kana dakuten), unify apostrophes, collapse spaces."""
    t = unicodedata.normalize("NFKD", (text or "").casefold().replace("’", "'").replace("‘", "'"))
    out = []
    for ch in t:
        if unicodedata.category(ch) == "Cf":  # zero-width / soft hyphen can split an injection marker
            continue
        if unicodedata.combining(ch) and out and out[-1] < "ɐ":
            continue
        out.append(ch)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", "".join(out))).strip()


_SENTENCE = re.compile(r"(?<=[.!?;。！？])\s*|\n")

_INJECTION = _rx(
    r"\b(?:ignore|disregard|forget)\b(?: \w+){0,3} (?:instructions?|rules|prompts?|guidelines)\b",
    r"\bmark (?:\w+ ){0,3}as (?:complete|completed|done|resolved|closed)\b",
    r"\bset (?:the )?status\b", r"(?:^|[\s<\[])(?:system|assistant|developer)\s*[:>\]]", r"\byou are now\b",
    r"\bnew instructions\b", r"\b(?:override|bypass)\b",
    r"\bignor\w* (?:\w+ ){0,2}(?:instrucciones|instrucoes|instructions|reglas|regras|consignes)\b",
    r"\bmarca\w* como (?:complet|conclu|termin)", r"\bmarque\w* comme (?:termine|complete)",
    r"指示を無視|命令を無視|完了としてマーク|完了にして", r"지시(?:사항)?를 무시|명령을 무시|완료로 표시|완료 처리",
)

_STEM = r"(?:delet|eras|remov|clos|cancel|elimin|borr|suprim|exclu|apag|cerr|encerr|suppr|effac|ferm|clotur)\w*"
_NEG_WORD = (r"(?:\b(?:do not|dont|don't|never|without|sem|sin|sans|ne)\b"
             r"|(?<!\bwas )(?<!\bwere )(?<!\bis )(?<!\bare )(?<!\bhas )(?<!\bhave )(?<!\bhad )(?<!\bbeen )\bnot\b"
             # ponytail: es/pt "no/nao" + aux lookahead; narrative negations beyond this list need the LLM path
             r"|\b(?:no|nao)\b(?! longer| more| fue| ha| han| se| foi| esta| estava| tem))")
_NEGATED = _rx(_NEG_WORD + r"(?: [\w'-]+){0,3}? " + _STEM, r"\bno (?:deletion|erasure)\b",
               r"(?:削除|退会|消去)(?:は|を)?(?:しないで|しない|不要|希望しません)",
               r"(?:삭제|탈퇴)(?:는|를|은)? ?(?:하지 ?마|하지 ?말|원하지 않|요청이 아닙)")

_DELETE = _rx(
    r"\bdelet(?:e|ed|es|ing|ion)\b", r"\beras(?:e|ed|es|ing|ure)\b", r"\bright to be forgotten\b|\bforget me\b",
    r"\bremov(?:e|ed|al|ing)\b(?: [\w'-]+){0,4}? (?:account|profile|personal|data|details|information|records?"
    r"|cop(?:y|ies)|name|traces|identifiers|search results?|files?|archives?|everything|rest)\b",
    r"\bclos(?:e|ed|ing|ure)\b(?: \w+){0,3}? account\b", r"\baccount\b.{0,60}\b(?:closed|removed)\b",
    r"\bexclu(?:ir|sao|am|a)\b", r"\bapag(?:ar|ue|uem)\b", r"\bremover\b", r"\bencerr\w* (?:a |minha )?conta\b",
    r"\belimin(?:ar|acion|en|e|ada|ado)\b", r"\bborr(?:ar|en|e|ado)\b", r"\bsuprim(?:ir|an)\b", r"\bsupresion\b",
    r"\bdar(?:me)? de baja (?:de )?(?:la |mi )cuenta\b", r"\bcerr\w* (?:la |mi )cuenta\b",
    r"\bsuppr(?:ession|imer|imez|ime)\b", r"\beffac(?:er|ez|ement)\b", r"\b(?:fermer|cloturer) (?:mon|le) compte\b",
    r"削除|消去|退会|抹消", r"삭제|탈퇴|파기",
)
# verification-style asks ("confirm the profile is gone"): deletion-leaning, but could be a restore complaint
_DELETE_WEAK = _rx(r"\bno longer (?:need|use|want)\b(?: \w+){0,2} account\b", r"\b(?:account|profile)\b(?: \w+){0,2} gone\b",
                   r"\b(?:cannot|can't|no longer) (?:identify|point back to) me\b")

_KEEP = _rx(
    r"\b(?:keep|leave)\b (?:the |my |this )?(?:account|profile)\b", r"\b(?:leave|keep)\b.{0,40}\b(?:active|in place|as it is)\b",
    r"\bstill (?:need|use|want)\b", r"\bcontinue (?:using|to use)\b",
    r"\bmanten\w* (?:la |mi )cuenta\b", r"\bmant(?:er|enha) (?:a |minha )conta\b", r"\b(?:garder|conserver) (?:mon|le) compte\b",
)
_OTHER = {
    "access": _rx(r"\b(?:send|give|provide|need|want|request|get|email) (?:me )?(?:a )?cop(?:y|ies)\b",
                  r"\bwhat (?:personal )?(?:information|data)\b.{0,30}\b(?:hold|have|store|keep)\b",
                  r"\binformation request\b", r"\baccess (?:request|to my)\b",
                  r"\bcopi[ae] (?:de|dos) (?:mis|meus|mes) (?:datos|dados|donnees)\b",
                  r"\bacc?es+o? (?:a|aos) (?:mis|meus|mes) (?:datos|dados|donnees)\b", r"開示|열람|사본"),
    "export": _rx(r"\bdownload (?:all )?my\b", r"\bportab", r"\bexport (?:all )?my\b", r"\bexportar\b", r"\bexporter\b",
                  r"エクスポート|내보내기"),
    "correction": _rx(r"\bmisspel", r"\bout of date\b|\boutdated\b|\btypo\b",
                      r"\b(?:correct|update|fix|rectify|replace)\b (?:it|my|the|this)\b",
                      r"\bchange (?:the|my) (?:e-?mail|name|surname|address|phone|number|password)\b",
                      r"\b(?:corregir|corrigir|corriger|actualizar|atualizar|rectificar|retificar|rectifier)\b",
                      r"\bmettre a jour\b", r"訂正|修正|정정|수정"),
    "opt_out": _rx(r"\bunsubscrib", r"\bopt(?:ed|ing)?(?: me)?[- ]?out\b", r"\b(?:promotional|marketing)\b",
                   r"\bnewsletters?\b", r"\bstop (?:the |all |sending )?(?:\w+ )?(?:e-?mails|messages|mails)\b",
                   r"\bdesabonn|\bdesinscri|\bdescadastr|\bpublicidad|\bpublicidade|\bboletin\b",
                   r"配信停止|メルマガ|広告|수신 ?거부|광고"),
    "login_help": _rx(r"\breset(?:ting)? (?:the |my )?(?:login|password)\b", r"\bcan't (?:access|log ?in)\b"),
}


def signals(text: str) -> dict:
    """Rule hits for `text` (also used for reporting reasons)."""
    sents = [s for s in _SENTENCE.split(normalize(text)) if s and s.strip()]
    clean = [s for s in sents if not _INJECTION.search(s)]
    t = " ".join(clean)
    negated = bool(_NEGATED.search(t))
    t = _NEGATED.sub(" ", t)
    return {"injection": len(clean) < len(sents), "negated": negated, "delete": bool(_DELETE.search(t)),
            "delete_weak": bool(_DELETE_WEAK.search(t)), "keep": bool(_KEEP.search(t)),
            "other": sorted(k for k, rx in _OTHER.items() if rx.search(t))}


def classify(text: str, offline: bool = True, client=None) -> Intent:
    """Rules first. The LLM runs only when online, a client is given and the rules are UNKNOWN or < 0.7 confident."""
    r = _rules(text)
    if offline or client is None or (r.label != "UNKNOWN" and r.confidence >= 0.7):
        return r
    try:
        label, conf, flags = _ask_llm(text, client)
    except Exception:  # LLMError, offline-cache miss, bad JSON, network: the rules result stands
        return r
    if "injection_marker" in r.flags:  # the LLM can never clear an injection flag
        flags = tuple(dict.fromkeys(flags + ("injection_marker",)))
    if label == "UNKNOWN":
        return Intent(r.label, r.confidence, "rules", r.flags + tuple(f for f in flags if f not in r.flags))
    return Intent(label, min(conf, 0.9), "llm", flags)


def _rules(text: str) -> Intent:
    s = signals(text)
    flags = ("injection_marker",) if s["injection"] else ()
    against = s["negated"] or s["keep"]
    if (s["delete"] or s["delete_weak"]) and against:
        return Intent("UNKNOWN", 0.3, "rules", flags)            # asks to delete and to keep: conflicting
    if s["delete"]:
        return Intent("DELETE", 0.8 if s["other"] else 0.95, "rules", flags)
    if s["delete_weak"]:
        return Intent("DELETE", 0.6, "rules", flags)
    if against:
        return Intent("NOT_DELETE", 0.95 if s["other"] else 0.9, "rules", flags)
    if s["other"]:
        return Intent("NOT_DELETE", 0.8, "rules", flags)
    return Intent("UNKNOWN", 0.0, "rules", flags)


_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "intent_classifier.md"
_SCHEMA = {"required": ["results"]}
_neighbour_cache: dict = {}


def _neighbours(text: str, client, k: int = 3) -> str:
    """k nearest sample request texts (rules label as the example label), by cosine similarity of query embeddings."""
    if id(client) not in _neighbour_cache:
        rows = [r["request_text"] for r in read_csv(DATASET / "sample_deletion_requests.csv")]
        rows = [t for t in rows if _rules(t).label != "UNKNOWN"]
        _neighbour_cache[id(client)] = (rows, client.embed(rows, input_type="query"))
    rows, vecs = _neighbour_cache[id(client)]
    q = client.embed([text], input_type="query")[0]

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b)) / ((sum(x * x for x in a) * sum(y * y for y in b)) ** 0.5 or 1)
    best = sorted(range(len(rows)), key=lambda i: -cos(q, vecs[i]))[:k]
    return "\n".join(f"{json.dumps(rows[i], ensure_ascii=False)} -> {_rules(rows[i]).label}" for i in best)


def _ask_llm(text: str, client) -> tuple[str, float, tuple]:
    try:
        neighbours = _neighbours(text, client)
    except Exception:
        neighbours = ""
    # request text is data: JSON-encoded inside the <requests> block, tag-closers neutralised
    safe = (text or "").replace("</requests>", "").replace("<requests>", "")
    prompt = (_PROMPT.read_text(encoding="utf-8").replace("{{neighbours}}", neighbours)
              .replace("{{requests}}", json.dumps([{"id": "1", "text": safe}], ensure_ascii=False)))
    out = client.complete("fast", [{"role": "user", "content": prompt}], schema=_SCHEMA, max_tokens=300)
    res = out["results"][0]
    label = res.get("label")
    if label not in LABELS:
        raise ValueError("bad label")
    flags = tuple(f for f in res.get("flags", []) if f == "injection_marker")
    return label, float(res.get("confidence", 0.5)), flags
