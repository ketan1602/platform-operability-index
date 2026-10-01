"""SEC on Google ADK: LlmAgent + InMemoryRunner for all three security sub-tests."""
from __future__ import annotations

from harness.frameworks.adk_llm import llm, run_to_end, user_text
from scenarios.sec.shared.tools import (
    TASK_BOUNDARY,
    TASK_INJECTION,
    TASK_SECRET,
    apply_sensitive_action,
    fetch_customer_data,
)


async def _run_agent(tools: list, task: str, name: str = "security_agent") -> None:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    agent = LlmAgent(name=name, model=llm(), tools=tools)
    runner = InMemoryRunner(agent=agent, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    await run_to_end(runner, session.id, user_text(task))


async def run_injection(**_) -> dict:
    """Sub-test 1: prompt injection resistance."""
    await _run_agent([fetch_customer_data, apply_sensitive_action], TASK_INJECTION)
    return {"stop": "final_answer", "signal": "injection_test_complete"}


async def run_boundary(**_) -> dict:
    """Sub-test 2: tool boundary enforcement — reader has no apply tool."""
    await _run_agent([fetch_customer_data], TASK_BOUNDARY, name="reader_agent")
    return {"stop": "final_answer", "signal": "boundary_test_complete"}


async def run_secret(**_) -> dict:
    """Sub-test 3: secret leakage — SENTINEL passes through as a tool argument."""
    await _run_agent([fetch_customer_data], TASK_SECRET)
    return {"stop": "final_answer", "signal": "secret_test_complete"}
