import json

import pytest

from ghost import llm

KEY = "nvapi-" + "d" * 30          # built at runtime so no key-shaped literal is committed
PARSE_KEY = "nvapi-" + "p" * 30
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    for var in ("NVIDIA_API_KEY", "NVIDIA_API_KEY_PARSE", "NVIDIA_API_KEY_RERANK", "NVIDIA_API_KEY_EMBED",
                "NVIDIA_API_KEY_EMBED_LARGE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", KEY)
    monkeypatch.setenv("NVIDIA_API_KEY_PARSE", PARSE_KEY)


class Fake:
    """Records calls; replies from a queue of (status, json-able body) or exceptions."""
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        status, payload = r
        return status, json.dumps(payload).encode()


def client(fake, tmp_path, **kw):
    return llm.Client(transport=fake, cache_dir=tmp_path / "cache", sleep=kw.pop("sleep", lambda s: None), **kw)


EMB = (200, {"data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}],
             "usage": {"prompt_tokens": 7, "total_tokens": 7}})


# --- config / secrets

def test_load_env_sets_only_missing_vars(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# comment\n\nNEW_VAR='abc'\nNVIDIA_API_KEY=from-file\n", encoding="utf-8")
    llm.load_env(f)
    import os
    assert os.environ["NEW_VAR"] == "abc" and os.environ["NVIDIA_API_KEY"] == KEY  # existing env wins
    monkeypatch.delenv("NEW_VAR")


def test_load_env_missing_file_is_fine(tmp_path):
    llm.load_env(tmp_path / "nope.env")


def test_api_key_role_override_then_default(monkeypatch):
    assert llm.api_key("parse") == PARSE_KEY
    assert llm.api_key("rerank") == KEY
    monkeypatch.delenv("NVIDIA_API_KEY")
    with pytest.raises(llm.LLMConfigError, match="NVIDIA_API_KEY_RERANK or NVIDIA_API_KEY") as e:
        llm.api_key("rerank")
    assert PARSE_KEY not in str(e.value)


# --- embeddings

def test_embed_payload_and_index_order(tmp_path):
    fake = Fake(EMB)
    c = client(fake, tmp_path)
    assert c.embed(["a", "b"], input_type="query") == [[1.0, 0.0], [0.0, 1.0]]
    call = fake.calls[0]
    body = json.loads(call["body"])
    assert call["url"] == "https://integrate.api.nvidia.com/v1/embeddings"
    assert body == {"input": ["a", "b"], "model": "nvidia/nemotron-3.5-embed-1b", "input_type": "query",
                    "encoding_format": "float", "truncate": "END"}
    assert call["headers"]["Authorization"] == f"Bearer {KEY}"
    assert c.usage[0] | {} == c.usage[0] and c.usage[0]["prompt_tokens"] == 7 and c.usage[0]["cached"] is False


def test_embed_large_uses_8b_model_and_its_key(tmp_path, monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY_EMBED_LARGE", "nvapi-" + "l" * 30)
    fake = Fake(EMB)
    client(fake, tmp_path).embed(["a", "b"], input_type="passage", large=True)
    assert json.loads(fake.calls[0]["body"])["model"] == "nvidia/nemotron-3.5-embed-8b"
    assert fake.calls[0]["headers"]["Authorization"].endswith("l" * 30)


def test_embed_rejects_bad_input_type(tmp_path):
    with pytest.raises(ValueError):
        client(Fake(), tmp_path).embed(["a"], input_type="document")


# --- rerank

def test_rerank_sorted_by_logit(tmp_path):
    fake = Fake((200, {"rankings": [{"index": 1, "logit": -5.0}, {"index": 0, "logit": 2.5}],
                       "usage": {"prompt_tokens": 30, "total_tokens": 30}}))
    assert client(fake, tmp_path).rerank("why?", ["p0", "p1"]) == [(0, 2.5), (1, -5.0)]
    body = json.loads(fake.calls[0]["body"])
    assert fake.calls[0]["url"] == "https://ai.api.nvidia.com/v1/retrieval/nvidia/nemotron-3.5-rerank-8b/reranking"
    assert body["query"] == {"text": "why?"} and body["passages"] == [{"text": "p0"}, {"text": "p1"}]
    assert body["truncate"] == "END"


# --- parse

def test_parse_page_multipart_and_parse_key(tmp_path):
    fake = Fake((200, {"content": "**backup_9287**", "finish_reason": "stop", "usage": {"output_tokens": 9}}))
    assert client(fake, tmp_path).parse_page(PNG) == "**backup_9287**"
    call = fake.calls[0]
    assert call["url"] == "https://ai.api.nvidia.com/v1/retrieval/nvidia/nemotron-3.5-parse/parse"
    assert call["headers"]["Authorization"] == f"Bearer {PARSE_KEY}"
    assert call["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="document"' in call["body"] and b"Content-Type: image/png" in call["body"] and PNG in call["body"]


@pytest.mark.parametrize("data", [b"GIF89a....", b"%PDF-1.7", b""])
def test_parse_page_rejects_non_png_jpeg_before_network(tmp_path, data):
    fake = Fake()
    with pytest.raises(ValueError):
        client(fake, tmp_path).parse_page(data)
    assert fake.calls == []


def test_parse_page_size_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(ValueError):
        client(Fake(), tmp_path).parse_page(PNG)


# --- cache, offline, retries, rate limit

def test_cache_hit_skips_network_and_cache_has_no_key(tmp_path):
    fake = Fake(EMB)
    c = client(fake, tmp_path)
    c.embed(["a", "b"], input_type="query")
    assert c.embed(["a", "b"], input_type="query") == [[1.0, 0.0], [0.0, 1.0]]
    assert len(fake.calls) == 1 and c.usage[-1]["cached"] is True
    blob = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "cache").rglob("*.json"))
    assert KEY not in blob and "nvapi-" not in blob


def test_offline_cache_miss_fails_closed(tmp_path):
    fake = Fake()
    with pytest.raises(llm.OfflineCacheMiss):
        client(fake, tmp_path, offline=True).embed(["a"], input_type="query")
    assert fake.calls == []


def test_retries_transient_then_succeeds(tmp_path):
    slept = []
    fake = Fake((503, {"message": "busy"}), TimeoutError("read timed out"), EMB)
    assert client(fake, tmp_path, sleep=slept.append).embed(["a", "b"], input_type="query")
    assert len(fake.calls) == 3 and len(slept) == 2


def test_gives_up_after_max_attempts(tmp_path):
    fake = Fake(*[(504, {"message": "timeout"})] * llm.MAX_ATTEMPTS)
    with pytest.raises(llm.LLMError, match="504"):
        client(fake, tmp_path).embed(["a"], input_type="query")


def test_client_error_not_retried_and_key_not_leaked(tmp_path):
    fake = Fake((401, {"message": f"bad key {KEY}"}))
    with pytest.raises(llm.LLMError) as e:
        client(fake, tmp_path).embed(["a"], input_type="query")
    assert len(fake.calls) == 1 and KEY not in str(e.value) and "401" in str(e.value)


def test_rate_limit_spaces_uncached_calls(tmp_path):
    slept, now = [], [100.0]
    fake = Fake(EMB, EMB)
    c = client(fake, tmp_path, rpm=60, sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)),
               clock=lambda: now[0])
    c.embed(["a", "b"], input_type="query")
    c.embed(["c", "d"], input_type="query")
    assert slept and abs(sum(slept) - 1.0) < 1e-6


def test_model_overrides_read_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBED_MODEL", "nvidia/some-other-embed")   # e.g. loaded from .env after import
    fake = Fake(EMB)
    client(fake, tmp_path).embed(["a", "b"], input_type="query")
    assert json.loads(fake.calls[0]["body"])["model"] == "nvidia/some-other-embed"
    assert llm.models()["embed"] == "nvidia/some-other-embed"
