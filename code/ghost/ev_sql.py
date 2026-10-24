"""SQL snapshot exports (24): docs/evidence_field_map.md §2.1. Run via safety.open_sandboxed_sqlite."""
from pathlib import Path


def parse(path: Path, meta: dict) -> tuple[list, list]:
    """-> (facts: list[evidence.Fact], coverage: list[evidence.Coverage]). Raise on malformed input.

    TODO(P1-05a): implement per the field map; import Fact/Coverage/system_for/norm_keys/is_null from .evidence
    inside the function (evidence imports this module).
    """
    return [], []
