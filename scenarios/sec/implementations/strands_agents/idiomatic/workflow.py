"""SEC on Strands: Agent event loop for all three security sub-tests."""
from __future__ import annotations

from harness.frameworks.strands_llm import model
from scenarios.sec.shared.tools import (
    TASK_BOUNDARY,
    TASK_INJECTION,
    TASK_SECRET,
    apply_sensitive_action,
    fetch_customer_data,
)


def _agent(tools: list):
    from strands import Agent, tool as strands_tool
    return Agent(
        model=model(),
        tools=[strands_tool(t) for t in tools],
        callback_handler=None,
    )


def run_injection(**_) -> dict:
    """Sub-test 1: prompt injection resistance."""
    _agent([fetch_customer_data, apply_sensitive_action])(TASK_INJECTION)
    return {"stop": "final_answer", "signal": "injection_test_complete"}


def run_boundary(**_) -> dict:
    """Sub-test 2: tool boundary enforcement — reader has no apply tool."""
    _agent([fetch_customer_data])(TASK_BOUNDARY)
    return {"stop": "final_answer", "signal": "boundary_test_complete"}


def run_secret(**_) -> dict:
    """Sub-test 3: secret leakage — SENTINEL passes through as a tool argument."""
    _agent([fetch_customer_data])(TASK_SECRET)
    return {"stop": "final_answer", "signal": "secret_test_complete"}
