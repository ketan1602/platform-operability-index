"""DX on OpenAI Agents SDK — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, broken_missing_arg, broken_noop, broken_return_type,
)


async def _run_agent(model, tool_fn, task: str) -> dict:
    from agents import Agent, Runner, function_tool

    agent = Agent(name="dx_agent", model=model, tools=[function_tool(tool_fn)])
    result = await Runner.run(agent, task)
    return {"stop": "final_answer", "answer": str(result.final_output)}


async def _mistake_a() -> dict:
    from harness.frameworks.openai_agents_llm import model
    return await _run_agent(model(), broken_return_type, TASK_WEATHER)


async def _mistake_b() -> dict:
    from harness.frameworks.openai_agents_llm import model
    return await _run_agent(model(), broken_missing_arg, TASK_WEATHER)


async def _mistake_c() -> dict:
    from agents import OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI
    set_tracing_disabled(True)
    client = AsyncOpenAI(base_url="not-a-valid-url", api_key="dummy")
    from harness.shared.llm import get_model
    mdl = OpenAIChatCompletionsModel(model=get_model(), openai_client=client)
    return await _run_agent(mdl, broken_noop, TASK_WEATHER)


_DISPATCH = {"A": _mistake_a, "B": _mistake_b, "C": _mistake_c}


async def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return await fn()
