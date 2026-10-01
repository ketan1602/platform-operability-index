from __future__ import annotations

from harness.shared.llm import openai_compat


def llm():
    from google.adk.models.lite_llm import LiteLlm
    c = openai_compat()
    # litellm strips one "openai/" provider prefix, so the provider's own model id needs another.
    return LiteLlm(model=f"openai/{c['model']}", api_base=c["base_url"], api_key=c["api_key"],
                   extra_headers=c["headers"], num_retries=0)


async def run_to_end(runner, session_id: str, message, run_config=None) -> list:
    events = []
    async for event in runner.run_async(user_id="poi", session_id=session_id,
                                        new_message=message, run_config=run_config):
        events.append(event)
    return events


def user_text(text: str):
    from google.genai import types
    return types.Content(role="user", parts=[types.Part(text=text)])
