"""The single seam for every NVIDIA build call (architecture.md §4.5). Stdlib HTTP only (T10).

Keys come from the environment (optionally loaded from the gitignored .env): NVIDIA_API_KEY, overridden per
endpoint by NVIDIA_API_KEY_<ROLE> (EMBED, EMBED_LARGE, RERANK, PARSE, CHAT). Every response is cached by
sha256(url + body) under .cache/llm; offline mode serves only from that cache and fails closed on a miss.
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .contract import REPO

# role -> (env var, default). Read at call time so a .env loaded after import still applies.
DEFAULT_MODELS = {
    "fast": ("LLM_MODEL_FAST", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    "reason": ("LLM_MODEL_REASON", "nvidia/nemotron-3-super-120b-a12b"),
    "vision": ("LLM_MODEL_VISION", "nvidia/nemotron-3.5-super-vl-120b-a12b"),
    "guard": ("GUARD_MODEL", "nvidia/llama-3.1-nemoguard-8b-topic-control"),
    "embed": ("EMBED_MODEL", "nvidia/nemotron-3.5-embed-1b"),
    "embed_large": ("EMBED_MODEL_LARGE", "nvidia/nemotron-3.5-embed-8b"),
    "rerank": ("RERANK_MODEL", "nvidia/nemotron-3.5-rerank-8b"),
    "parse": ("PARSE_MODEL", "nvidia/nemotron-3.5-parse"),
}


def model(role: str) -> str:
    var, default = DEFAULT_MODELS[role]
    return os.environ.get(var, default)


def models() -> dict[str, str]:
    return {role: model(role) for role in DEFAULT_MODELS}


def base_url() -> str:
    return os.environ.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")


def retrieval_url() -> str:
    return os.environ.get("RETRIEVAL_BASE_URL", "https://ai.api.nvidia.com/v1/retrieval")
MAX_ATTEMPTS = 3
TIMEOUT_S = 150                      # embed-8b cold starts exceed 60 s on the free tier
MAX_IMAGE_BYTES = 20 * 1024 * 1024   # parse accepts 100 MiB; evidence pages are far smaller (T6)
RETRYABLE = {429, 500, 502, 503, 504}
_KEY_PATTERN = re.compile(r"nvapi-[A-Za-z0-9_\-]+")


class LLMError(RuntimeError):
    pass


class LLMConfigError(LLMError):
    pass


class OfflineCacheMiss(LLMError):
    pass


def load_env(path: Path = REPO / ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, comments ignored, existing environment always wins."""
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key, value.strip().strip("'\""))


def api_key(role: str) -> str:
    specific = f"NVIDIA_API_KEY_{role.upper()}"
    key = os.environ.get(specific) or os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise LLMConfigError(f"no API key: set {specific} or NVIDIA_API_KEY in the environment or .env")
    return key


def _redact(text: str) -> str:
    return _KEY_PATTERN.sub("nvapi-[REDACTED]", text)


def urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise TimeoutError(str(e.reason)) from None


def _image_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise ValueError("parse accepts only PNG or JPEG page images")


class Client:
    def __init__(self, *, transport=urllib_transport, cache_dir: Path = REPO / ".cache" / "llm", offline: bool = False,
                 rpm: int | None = None, sleep=time.sleep, clock=time.monotonic):
        self.transport, self.cache_dir, self.offline = transport, Path(cache_dir), offline
        rpm = int(os.environ.get("LLM_RPM", 35)) if rpm is None else rpm
        self.min_interval = 60.0 / rpm if rpm else 0.0
        self.sleep, self.clock, self._last = sleep, clock, None
        self.usage: list[dict] = []

    # ---------------------------------------------------------------- public endpoints

    def embed(self, texts: list[str], *, input_type: str, large: bool = False, case_id: str | None = None) -> list[list[float]]:
        if input_type not in ("query", "passage"):
            raise ValueError("input_type must be 'query' or 'passage'")
        role = "embed_large" if large else "embed"
        body = {"input": list(texts), "model": model(role), "input_type": input_type,
                "encoding_format": "float", "truncate": "END"}
        out = self._call(role, f"{base_url()}/embeddings", json.dumps(body).encode(), "application/json", case_id)
        return [d["embedding"] for d in sorted(out["data"], key=lambda d: d["index"])]

    def rerank(self, query: str, passages: list[str], *, case_id: str | None = None) -> list[tuple[int, float]]:
        name = model("rerank")
        body = {"model": name, "query": {"text": query}, "passages": [{"text": p} for p in passages], "truncate": "END"}
        out = self._call("rerank", f"{retrieval_url()}/{name}/reranking", json.dumps(body).encode(), "application/json", case_id)
        return sorted(((r["index"], r["logit"]) for r in out["rankings"]), key=lambda r: -r[1])

    def parse_page(self, image: bytes, *, max_output_tokens: int = 9000, case_id: str | None = None) -> str:
        """One rendered page (PNG/JPEG) -> Markdown with layout tags (<x_..><y_..>, <class_..>, LaTeX tables)."""
        if len(image) > MAX_IMAGE_BYTES:
            raise ValueError(f"image over {MAX_IMAGE_BYTES} bytes")
        mime = _image_mime(image)
        boundary = "ghost" + hashlib.sha256(image).hexdigest()[:24]  # deterministic, so the cache key is stable
        options = json.dumps({"decoding": {"max_output_tokens": max_output_tokens}})
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="page"\r\n'
                f"Content-Type: {mime}\r\n\r\n").encode() + image + (
                f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="options"\r\n'
                f"Content-Type: application/json\r\n\r\n{options}\r\n--{boundary}--\r\n").encode()
        name = model("parse")
        out = self._call("parse", f"{retrieval_url()}/{name}/parse", body, f"multipart/form-data; boundary={boundary}", case_id)
        return out["content"]

    def complete(self, role: str, messages: list[dict], **kw) -> dict:
        raise NotImplementedError("P2-01: chat completions (disable reasoning via chat_template_kwargs)")

    # ---------------------------------------------------------------- plumbing

    def _call(self, role: str, url: str, body: bytes, content_type: str, case_id) -> dict:
        digest = hashlib.sha256(url.encode() + b"\n" + body).hexdigest()
        cached = self.cache_dir / digest[:2] / f"{digest}.json"
        if cached.is_file():
            out = json.loads(cached.read_text(encoding="utf-8"))
            self._meter(role, out, True, case_id)
            return out
        if self.offline:
            raise OfflineCacheMiss(f"{role}: no cached response for {digest[:12]} (run with --online)")

        self._throttle()
        headers = {"Authorization": f"Bearer {api_key(role)}", "Content-Type": content_type, "Accept": "application/json"}
        last = ""
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                self.sleep(2 ** (attempt - 1))
            try:
                status, raw = self.transport(url, headers, body, TIMEOUT_S)
            except TimeoutError as e:
                last = f"timeout: {e}"
                continue
            if status == 200:
                out = json.loads(raw)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps(out), encoding="utf-8")
                self._meter(role, out, False, case_id)
                return out
            last = f"HTTP {status}: {_redact(raw[:300].decode('utf-8', 'replace'))}"
            if status not in RETRYABLE:
                break
        raise LLMError(f"{role} {model(role)} failed: {last}")

    def _throttle(self) -> None:
        if self.min_interval and self._last is not None:
            wait = self.min_interval - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def _meter(self, role: str, out: dict, cached: bool, case_id) -> None:
        u = out.get("usage", {})
        self.usage.append({"provider": "nvidia", "role": role, "model": model(role), "cached": cached,
                           "prompt_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("output_tokens", 0),
                           "total_tokens": u.get("total_tokens", u.get("prompt_tokens", 0) + u.get("output_tokens", 0)),
                           "case_id": case_id})
