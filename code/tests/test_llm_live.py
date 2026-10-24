"""Live smoke test against NVIDIA build. Opt-in: RUN_LIVE=1 python -m pytest code/tests/test_llm_live.py -q"""
import os

import pytest

from ghost import llm
from ghost.contract import DATASET

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to call NVIDIA build")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    llm.load_env()
    return llm.Client(cache_dir=tmp_path_factory.mktemp("live-cache"))


def test_embed_1b(client):
    v = client.embed(["please delete my account", "export my data"], input_type="query")
    assert len(v) == 2 and len(v[0]) == 2048


def test_rerank(client):
    ranked = client.rerank("Why was the deletion incomplete?",
                           ["The weather was sunny.", "A sync job recreated the support record after deletion."])
    assert ranked[0][0] == 1


def test_parse_evidence_screenshot(client):
    png = (DATASET / "evidence/images/backup_restore_console_20260429.png").read_bytes()
    assert "backup" in client.parse_page(png, max_output_tokens=2048)
