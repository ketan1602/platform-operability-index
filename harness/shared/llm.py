"""AI Refinery LLM wrapper — usable by all framework adapters.

All optional-dependency imports (air, langchain_openai, openai) are deferred
inside the function bodies so the harness core works without them installed.
"""
from __future__ import annotations
import os

import structlog

log = structlog.get_logger(__name__)

_DEFAULT_MODEL = "openai/gpt-oss-120b"


def _require_api_key() -> str:
    key = os.environ.get("AIREFINERY_API_KEY", "")
    if not key:
        raise RuntimeError("AIREFINERY_API_KEY must be set (see .env.example)")
    return key


def _require_base_url() -> str:
    url = os.environ.get("AIREFINERY_BASE_URL", "")
    if not url:
        raise RuntimeError(
            "AIREFINERY_BASE_URL must be set for OpenAI-compatible access (see .env.example)"
        )
    return url


def get_model() -> str:
    return os.environ.get("AIREFINERY_MODEL", _DEFAULT_MODEL)


def get_air_client():
    from air import AIRefinery  # noqa: PLC0415
    return AIRefinery(api_key=_require_api_key())


def get_air_async_client():
    from air import AsyncAIRefinery  # noqa: PLC0415
    return AsyncAIRefinery(api_key=_require_api_key())


def chat_complete(messages: list[dict], **kwargs) -> str:
    """Synchronous completion via AI Refinery; returns the assistant content string."""
    client = get_air_client()
    model = kwargs.pop("model", get_model())
    response = client.chat.completions.create(
        messages=messages,
        model=model,
        **kwargs,
    )
    content: str = response.choices[0].message.content
    log.info(
        "chat_complete.ok",
        model=model,
        prompt_tokens=getattr(response.usage, "prompt_tokens", None),
        completion_tokens=getattr(response.usage, "completion_tokens", None),
    )
    return content


def make_langchain_llm():
    """Return a ChatOpenAI instance pointed at AI Refinery.

    Requires AIREFINERY_BASE_URL and AIREFINERY_API_KEY.
    """
    from langchain_openai import ChatOpenAI  # noqa: PLC0415
    return ChatOpenAI(
        base_url=_require_base_url(),
        api_key=_require_api_key(),
        model=get_model(),
    )


def make_openai_client():
    """Return an openai.OpenAI client pointed at AI Refinery.

    Requires AIREFINERY_BASE_URL and AIREFINERY_API_KEY.
    """
    import openai  # noqa: PLC0415
    return openai.OpenAI(
        base_url=_require_base_url(),
        api_key=_require_api_key(),
    )
