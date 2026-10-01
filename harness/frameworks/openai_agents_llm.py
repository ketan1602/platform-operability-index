from __future__ import annotations

from harness.shared.llm import openai_compat


def model():
    from agents import OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI
    # The SDK's own tracing exports to api.openai.com by default; keep benchmark data local.
    set_tracing_disabled(True)
    c = openai_compat()
    client = AsyncOpenAI(base_url=c["base_url"], api_key=c["api_key"], default_headers=c["headers"])
    return OpenAIChatCompletionsModel(model=c["model"], openai_client=client)
