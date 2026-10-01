"""PORT on Strands: sub-tests 2 (isolation) and 3 (tool extensibility)."""
from __future__ import annotations

from harness.frameworks.strands_llm import model
from scenarios.port.shared.tools import (
    AGENT_NAME, TASK_FETCH_TPL, TASK_WEATHER, fetch_data, get_weather,
)


def _run_tool_ext() -> dict:
    from strands import Agent, tool

    agent = Agent(name=AGENT_NAME, model=model(), tools=[tool(get_weather)], callback_handler=None)
    result = agent(TASK_WEATHER)
    return {"stop": "final_answer", "sub_test": "tool_ext", "answer": str(result)}


def _run_isolation(run_id: str) -> dict:
    from strands import Agent, tool

    agent = Agent(name=AGENT_NAME, model=model(), tools=[tool(fetch_data)], callback_handler=None)
    task = TASK_FETCH_TPL.format(run_id=run_id)
    result = agent(task)
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id, "answer": str(result)}


def run(*, sub_test: str = "tool_ext", run_id: str = "", **_) -> dict:
    if sub_test == "isolation":
        return _run_isolation(run_id)
    return _run_tool_ext()
