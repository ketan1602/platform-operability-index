"""SEC on LangGraph: prebuilt ReAct agent for all three security sub-tests."""
from __future__ import annotations

from harness.frameworks.langgraph_llm import chat_model
from scenarios.sec.shared.tools import (
    TASK_BOUNDARY,
    TASK_INJECTION,
    TASK_SECRET,
    apply_sensitive_action,
    fetch_customer_data,
)


def _agent(tools: list, name: str = "security_agent"):
    from langchain_core.tools import tool as lc_tool
    from langgraph.prebuilt import create_react_agent
    return create_react_agent(
        chat_model(),
        [lc_tool(t) for t in tools],
        name=name,
    )


def run_injection(**_) -> dict:
    """Sub-test 1: prompt injection resistance."""
    agent = _agent([fetch_customer_data, apply_sensitive_action])
    agent.invoke({"messages": [("user", TASK_INJECTION)]})
    return {"stop": "final_answer", "signal": "injection_test_complete"}


def run_boundary(**_) -> dict:
    """Sub-test 2: tool boundary enforcement — reader has no apply tool."""
    reader = _agent([fetch_customer_data], name="reader_agent")
    reader.invoke({"messages": [("user", TASK_BOUNDARY)]})
    return {"stop": "final_answer", "signal": "boundary_test_complete"}


def run_secret(**_) -> dict:
    """Sub-test 3: secret leakage — SENTINEL passes through as a tool argument."""
    agent = _agent([fetch_customer_data])
    agent.invoke({"messages": [("user", TASK_SECRET)]})
    return {"stop": "final_answer", "signal": "secret_test_complete"}
