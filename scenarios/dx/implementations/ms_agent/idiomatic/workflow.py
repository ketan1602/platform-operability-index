"""DX on AutoGen — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, broken_missing_arg, broken_noop, broken_return_type,
)


async def _agent_run(client, tool_fn, task: str) -> dict:
    from autogen_agentchat.agents import AssistantAgent

    agent = AssistantAgent("dx_agent", model_client=client, tools=[tool_fn],
                           reflect_on_tool_use=True)
    result = await agent.run(task=task)
    return {"stop": "final_answer", "answer": str(result.messages[-1].content)}


async def _mistake_a() -> dict:
    from harness.frameworks.autogen_llm import chat_client
    return await _agent_run(chat_client(), broken_return_type, TASK_WEATHER)


async def _mistake_b() -> dict:
    from harness.frameworks.autogen_llm import chat_client
    return await _agent_run(chat_client(), broken_missing_arg, TASK_WEATHER)


async def _mistake_c() -> dict:
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from autogen_core.models import ModelFamily, ModelInfo
    info = ModelInfo(vision=False, function_calling=True, json_output=True,
                     family=ModelFamily.UNKNOWN, structured_output=True)
    client = OpenAIChatCompletionClient(model="gpt-4o", base_url="not-a-valid-url",
                                        api_key="dummy", model_info=info)
    return await _agent_run(client, broken_noop, TASK_WEATHER)


_DISPATCH = {"A": _mistake_a, "B": _mistake_b, "C": _mistake_c}


async def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return await fn()
