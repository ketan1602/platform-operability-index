"""SEC on the OpenAI Agents SDK: Agent + Runner for all three security sub-tests."""
from __future__ import annotations

from harness.frameworks.openai_agents_llm import model
from scenarios.sec.shared.tools import (
    TASK_BOUNDARY,
    TASK_INJECTION,
    TASK_SECRET,
    apply_sensitive_action,
    fetch_customer_data,
)


def _agent(tools: list, name: str = "security_agent"):
    from agents import Agent, function_tool
    return Agent(
        name=name,
        model=model(),
        tools=[function_tool(t) for t in tools],
    )


async def run_injection(**_) -> dict:
    """Sub-test 1: prompt injection resistance."""
    from agents import Runner
    agent = _agent([fetch_customer_data, apply_sensitive_action])
    await Runner.run(agent, TASK_INJECTION)
    return {"stop": "final_answer", "signal": "injection_test_complete"}


async def run_boundary(**_) -> dict:
    """Sub-test 2: tool boundary enforcement — reader has no apply tool."""
    from agents import Runner
    reader = _agent([fetch_customer_data], name="reader_agent")
    await Runner.run(reader, TASK_BOUNDARY)
    return {"stop": "final_answer", "signal": "boundary_test_complete"}


async def run_secret(**_) -> dict:
    """Sub-test 3: secret leakage — SENTINEL passes through as a tool argument."""
    from agents import Runner
    agent = _agent([fetch_customer_data])
    await Runner.run(agent, TASK_SECRET)
    return {"stop": "final_answer", "signal": "secret_test_complete"}
