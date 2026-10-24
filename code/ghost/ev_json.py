"""JSON evidence (28): docs/evidence_field_map.md §2.2 and §2.5 ledger rows."""
from pathlib import Path


def parse(path: Path, meta: dict) -> tuple[list, list]:
    """-> (facts: list[evidence.Fact], coverage: list[evidence.Coverage]). Raise on malformed input.

    TODO(P1-05b): implement per the field map; import Fact/Coverage/system_for/norm_keys/is_null from .evidence
    inside the function (evidence imports this module).
    """
    return [], []
