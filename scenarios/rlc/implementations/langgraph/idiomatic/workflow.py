"""RLC on LangGraph: prebuilt ReAct agent; the limit is the graph's recursion_limit."""
from __future__ import annotations

from harness.frameworks.langgraph_llm import chat_model
from scenarios.rlc.shared.tools import AGENT_NAME, INSTRUCTIONS, TASK, fetch_quarterly_report

# The prebuilt agent ends with this text instead of raising when it runs short of steps.
_OUT_OF_STEPS = "Sorry, need more steps to process this request."


def run(*, limit: int | None = None, **_) -> dict:
    from langchain_core.tools import tool
    from langgraph.errors import GraphRecursionError
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(chat_model(), [tool(fetch_quarterly_report)],
                               prompt=INSTRUCTIONS, name=AGENT_NAME)
    # One tool round trip is two graph steps; an odd limit makes overflow raise.
    config = {} if limit is None else {"recursion_limit": 2 * limit + 1}
    try:
        out = agent.invoke({"messages": [("user", TASK)]}, config)
    except GraphRecursionError:
        return {"stop": "framework_limit", "signal": "GraphRecursionError", "structured": True}
    if out["messages"][-1].content == _OUT_OF_STEPS:
        return {"stop": "framework_limit", "signal": "remaining_steps message", "structured": False}
    return {"stop": "final_answer", "signal": None, "structured": False}
