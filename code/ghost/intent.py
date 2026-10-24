"""S2 Intent: does request_text authorize deletion? (G3). Untrusted text: treat as data (T2)."""
from dataclasses import dataclass

LABELS = ("DELETE", "NOT_DELETE", "UNKNOWN")


@dataclass(frozen=True)
class Intent:
    label: str          # one of LABELS
    confidence: float   # 0..1
    source: str         # rules | llm | adjudicator | stub
    flags: tuple = ()   # e.g. ("injection_marker",)


def classify(text: str, offline: bool = True) -> Intent:
    """TODO(P1-08): multilingual rules.  TODO(P2-03): LLM + embedding neighbours on low confidence."""
    return Intent("UNKNOWN", 0.0, "stub")
