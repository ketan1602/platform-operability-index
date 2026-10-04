"""Provider-agnostic LLM wrapper — usable by all framework adapters.

Priority order for configuration:
  1. Generic vars: LLM_BASE_URL, LLM_API_KEY, MODEL_ID  (preferred; works with any provider)
  2. Legacy alias vars: AIREFINERY_BASE_URL, AIREFINERY_API_KEY, AIREFINERY_MODEL
     (backwards-compat; accepted as fallback when the generic vars are absent)

All optional-dependency imports (air, langchain_openai, openai) are deferred
inside function bodies so the harness core works without them installed.
"""
from __future__ import annotations
import os

import structlog

log = structlog.get_logger(__name__)

_DEFAULT_MODEL = "gpt-4o"


def _require_api_key() -> str:
    key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("AIREFINERY_API_KEY")
        or ""
    )
    if not key:
        raise RuntimeError(
            "LLM_API_KEY must be set. "
            "See .env.example for OpenAI, Anthropic, and self-hosted endpoint examples."
        )
    return key


def _require_base_url() -> str:
    url = (
        os.environ.get("LLM_BASE_URL")
        or os.environ.get("AIREFINERY_BASE_URL")
        or ""
    )
    if not url:
        raise RuntimeError(
            "LLM_BASE_URL must be set (e.g. https://api.openai.com/v1). "
            "See .env.example for all supported providers."
        )
    return url


def get_model() -> str:
    return (
        os.environ.get("MODEL_ID")
        or os.environ.get("AIREFINERY_MODEL")
        or _DEFAULT_MODEL
    )


def _is_anthropic() -> bool:
    return "anthropic.com" in _require_base_url()


def _extra_headers() -> dict:
    """Return any provider-specific headers (e.g. sdk_version for enterprise LLM gateways)."""
    version = os.environ.get("AIREFINERY_SDK_VERSION", "")
    if version:
        return {"sdk_version": version}
    return {}


def get_air_client():
    """Native AIRefinery SDK client (requires airefinery-sdk extra)."""
    from air import AIRefinery  # noqa: PLC0415
    return AIRefinery(api_key=_require_api_key())


def get_air_async_client():
    from air import AsyncAIRefinery  # noqa: PLC0415
    return AsyncAIRefinery(api_key=_require_api_key())


def chat_complete(messages: list[dict], **kwargs) -> str:
    """Synchronous completion via any OpenAI-compatible endpoint.

    Falls back to the Anthropic SDK when LLM_BASE_URL contains anthropic.com.
    Returns the assistant content string.
    """
    model = kwargs.pop("model", get_model())
    if _is_anthropic():
        return _chat_complete_anthropic(messages, model=model, **kwargs)
    return _chat_complete_openai(messages, model=model, **kwargs)


def _chat_complete_openai(messages: list[dict], model: str, **kwargs) -> str:
    import openai  # noqa: PLC0415
    client = openai.OpenAI(
        base_url=_require_base_url(),
        api_key=_require_api_key(),
        default_headers=_extra_headers(),
    )
    response = client.chat.completions.create(messages=messages, model=model, **kwargs)
    content: str = response.choices[0].message.content
    log.info(
        "chat_complete.ok",
        provider="openai_compat",
        model=model,
        prompt_tokens=getattr(response.usage, "prompt_tokens", None),
        completion_tokens=getattr(response.usage, "completion_tokens", None),
    )
    return content


def _chat_complete_anthropic(messages: list[dict], model: str, **kwargs) -> str:
    import anthropic  # noqa: PLC0415
    client = anthropic.Anthropic(api_key=_require_api_key())
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_msgs = [m for m in messages if m["role"] != "system"]
    extra: dict = {}
    if system:
        extra["system"] = system
    max_tokens = kwargs.pop("max_tokens", 4096)
    response = client.messages.create(
        model=model,
        messages=user_msgs,
        max_tokens=max_tokens,
        **extra,
        **kwargs,
    )
    content: str = response.content[0].text
    log.info(
        "chat_complete.ok",
        provider="anthropic",
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    return content


def make_langchain_llm():
    """Return a ChatOpenAI (or ChatAnthropic) instance for the configured provider."""
    if _is_anthropic():
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
        return ChatAnthropic(
            anthropic_api_key=_require_api_key(),
            model_name=get_model(),
        )
    from langchain_openai import ChatOpenAI  # noqa: PLC0415
    return ChatOpenAI(
        base_url=_require_base_url(),
        api_key=_require_api_key(),
        model=get_model(),
        default_headers=_extra_headers(),
    )


def make_openai_client():
    """Return an openai.OpenAI client for the configured endpoint."""
    import openai  # noqa: PLC0415
    return openai.OpenAI(
        base_url=_require_base_url(),
        api_key=_require_api_key(),
        default_headers=_extra_headers(),
    )


def openai_compat() -> dict:
    """Settings every framework needs to reach the configured OpenAI-compatible API.

    Returns base_url, api_key, model, and any provider-specific headers.
    AIREFINERY_SDK_VERSION (if set) is forwarded automatically via _extra_headers().
    """
    return {
        "base_url": _require_base_url(),
        "api_key": _require_api_key(),
        "model": get_model(),
        "headers": _extra_headers(),
    }
