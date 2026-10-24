"""Logs (26) and TXT ledger (1): docs/evidence_field_map.md §2.3, §2.4, §2.5. Join started/completed lines on trace id."""
from pathlib import Path


def parse(path: Path, meta: dict) -> tuple[list, list]:
    """-> (facts: list[evidence.Fact], coverage: list[evidence.Coverage]). Raise on malformed input.

    TODO(P1-05c): implement per the field map; import Fact/Coverage/system_for/norm_keys/is_null from .evidence
    inside the function (evidence imports this module).
    """
    return [], []
