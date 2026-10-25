import importlib.util
from pathlib import Path

import pytest

_p = Path(__file__).resolve().parents[1] / "evaluation" / "custom_cases.py"
_spec = importlib.util.spec_from_file_location("custom_cases_runner", _p)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)


@pytest.mark.parametrize("build", cc.CASES, ids=lambda b: b.__name__)
def test_custom_case(build):
    ok, problems, _ = cc.check(build())
    assert ok, problems
