"""PORT on AutoGen: sub-tests 2 (isolation) and 3 (tool extensibility)."""
from __future__ import annotations

from harness.frameworks.autogen_llm import chat_client
from scenarios.port.shared.tools import (
    AGENT_NAME, TASK_FETCH_TPL, TASK_WEATHER, fetch_data, get_weather,
)


async def _run_tool_ext() -> dict:
    from autogen_agentchat.agents import AssistantAgent

    agent = AssistantAgent(AGENT_NAME, model_client=chat_client(),
                           tools=[get_weather], reflect_on_tool_use=True)
    result = await agent.run(task=TASK_WEATHER)
    return {"stop": "final_answer", "sub_test": "tool_ext",
            "answer": str(result.messages[-1].content)}


async def _run_isolation(run_id: str) -> dict:
    from autogen_agentchat.agents import AssistantAgent

    agent = AssistantAgent(AGENT_NAME, model_client=chat_client(),
                           tools=[fetch_data], reflect_on_tool_use=True)
    task = TASK_FETCH_TPL.format(run_id=run_id)
    result = await agent.run(task=task)
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
            "answer": str(result.messages[-1].content)}


async def run(*, sub_test: str = "tool_ext", run_id: str = "", **_) -> dict:
    if sub_test == "isolation":
        return await _run_isolation(run_id)
    return await _run_tool_ext()
