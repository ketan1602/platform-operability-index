"""PORT on the OpenAI Agents SDK: sub-tests 2 (isolation) and 3 (tool extensibility)."""
from __future__ import annotations

from harness.frameworks.openai_agents_llm import model
from scenarios.port.shared.tools import (
    AGENT_NAME, TASK_FETCH_TPL, TASK_WEATHER, fetch_data, get_weather,
)


async def _run_tool_ext() -> dict:
    from agents import Agent, Runner, function_tool

    agent = Agent(name=AGENT_NAME, model=model(), tools=[function_tool(get_weather)])
    result = await Runner.run(agent, TASK_WEATHER)
    return {"stop": "final_answer", "sub_test": "tool_ext", "answer": str(result.final_output)}


async def _run_isolation(run_id: str) -> dict:
    from agents import Agent, Runner, function_tool

    agent = Agent(name=AGENT_NAME, model=model(), tools=[function_tool(fetch_data)])
    task = TASK_FETCH_TPL.format(run_id=run_id)
    result = await Runner.run(agent, task)
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
            "answer": str(result.final_output)}


async def run(*, sub_test: str = "tool_ext", run_id: str = "", **_) -> dict:
    if sub_test == "isolation":
        return await _run_isolation(run_id)
    return await _run_tool_ext()
