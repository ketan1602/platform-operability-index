"""PORT on LangGraph: sub-tests 2 (isolation) and 3 (tool extensibility)."""
from __future__ import annotations

from harness.frameworks.langgraph_llm import chat_model
from scenarios.port.shared.tools import (
    AGENT_NAME, TASK_FETCH_TPL, TASK_WEATHER, fetch_data, get_weather,
)


def _run_tool_ext() -> dict:
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(chat_model(), [tool(get_weather)], name=AGENT_NAME)
    out = agent.invoke({"messages": [("user", TASK_WEATHER)]})
    return {"stop": "final_answer", "sub_test": "tool_ext", "answer": out["messages"][-1].content}


def _run_isolation(run_id: str) -> dict:
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(chat_model(), [tool(fetch_data)], name=AGENT_NAME)
    task = TASK_FETCH_TPL.format(run_id=run_id)
    out = agent.invoke({"messages": [("user", task)]})
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
            "answer": out["messages"][-1].content}


def run(*, sub_test: str = "tool_ext", run_id: str = "", **_) -> dict:
    if sub_test == "isolation":
        return _run_isolation(run_id)
    return _run_tool_ext()
