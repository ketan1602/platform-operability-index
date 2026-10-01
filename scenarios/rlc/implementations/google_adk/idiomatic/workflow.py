"""RLC on Google ADK: LlmAgent under a Runner; the limit is RunConfig.max_llm_calls."""
from __future__ import annotations

from harness.frameworks.adk_llm import llm, run_to_end, user_text
from scenarios.rlc.shared.tools import AGENT_NAME, INSTRUCTIONS, TASK, fetch_quarterly_report


async def run(*, limit: int | None = None, **_) -> dict:
    from google.adk.agents import LlmAgent, RunConfig
    from google.adk.agents.invocation_context import LlmCallsLimitExceededError
    from google.adk.runners import InMemoryRunner

    agent = LlmAgent(name=AGENT_NAME, model=llm(), instruction=INSTRUCTIONS,
                     tools=[fetch_quarterly_report])
    runner = InMemoryRunner(agent=agent, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    config = RunConfig() if limit is None else RunConfig(max_llm_calls=limit)
    try:
        await run_to_end(runner, session.id, user_text(TASK), config)
    except LlmCallsLimitExceededError:
        return {"stop": "framework_limit", "signal": "LlmCallsLimitExceededError", "structured": True}
    return {"stop": "final_answer", "signal": None, "structured": False}
