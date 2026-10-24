"""Provider-agnostic LLM seam (OpenAI-compatible; default NVIDIA build). All model calls go through here.

TODO(P2-01): sha256 cache under .cache/llm, token bucket (LLM_RPM), retry on 429/5xx, usage meter
(runs/<id>/usage.jsonl), --offline = cache only and fail closed on a miss. Key from NVIDIA_API_KEY only.
"""
import os

BASE_URL = os.environ.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODELS = {
    "fast": os.environ.get("LLM_MODEL_FAST", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    "reason": os.environ.get("LLM_MODEL_REASON", "nvidia/nemotron-3-super-120b-a12b"),
    "vision": os.environ.get("LLM_MODEL_VISION", "nvidia/nemotron-3.5-super-vl-120b-a12b"),
    "embed": os.environ.get("EMBED_MODEL", "nvidia/nemotron-3.5-embed-1b"),
    "guard": os.environ.get("GUARD_MODEL", "nvidia/llama-3.1-nemoguard-8b-topic-control"),
}


def complete(role: str, messages: list[dict], *, schema: dict | None = None, case_id: str | None = None) -> dict:
    raise NotImplementedError("P2-01")


def embed(texts: list[str]) -> list[list[float]]:
    raise NotImplementedError("P2-01")
