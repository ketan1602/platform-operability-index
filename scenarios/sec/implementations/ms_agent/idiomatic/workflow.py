"""SEC on AutoGen: AssistantAgent for all three security sub-tests."""
from __future__ import annotations

from harness.frameworks.autogen_llm import chat_client
from scenarios.sec.shared.tools import (
    TASK_BOUNDARY,
    TASK_INJECTION,
    TASK_SECRET,
    apply_sensitive_action,
    fetch_customer_data,
)


def _agent(tools: list, name: str = "security_agent"):
    from autogen_agentchat.agents import AssistantAgent
    return AssistantAgent(name, model_client=chat_client(), tools=tools)


async def run_injection(**_) -> dict:
    """Sub-test 1: prompt injection resistance."""
    agent = _agent([fetch_customer_data, apply_sensitive_action])
    await agent.run(task=TASK_INJECTION)
    return {"stop": "final_answer", "signal": "injection_test_complete"}


async def run_boundary(**_) -> dict:
    """Sub-test 2: tool boundary enforcement — reader has no apply tool."""
    reader = _agent([fetch_customer_data], name="reader_agent")
    await reader.run(task=TASK_BOUNDARY)
    return {"stop": "final_answer", "signal": "boundary_test_complete"}


async def run_secret(**_) -> dict:
    """Sub-test 3: secret leakage — SENTINEL passes through as a tool argument."""
    agent = _agent([fetch_customer_data])
    await agent.run(task=TASK_SECRET)
    return {"stop": "final_answer", "signal": "secret_test_complete"}
