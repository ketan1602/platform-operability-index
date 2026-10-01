"""AHQ on Google ADK: FunctionTool(require_confirmation=True), DatabaseSessionService on Postgres."""
from __future__ import annotations
import os

from harness.frameworks.adk_llm import llm, run_to_end, user_text
from scenarios.ahq.shared.tools import (AGENT_NAME, INSTRUCTIONS, TASK, apply_plan_change, digest,
                                        lookup_account)

CUSTOM_STORE = False
BACKEND = "postgres (DatabaseSessionService)"
_CONFIRM = "adk_request_confirmation"


def _runner():
    from google.adk.agents import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import DatabaseSessionService
    from google.adk.tools import FunctionTool

    agent = LlmAgent(name=AGENT_NAME, model=llm(), instruction=INSTRUCTIONS,
                     tools=[lookup_account, FunctionTool(apply_plan_change, require_confirmation=True)])
    # SQLAlchemy async engine: psycopg 3 driver.
    url = os.environ["POSTGRES_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
    return Runner(app_name="poi", agent=agent, session_service=DatabaseSessionService(db_url=url))


def _confirmation(events):
    calls = [c for e in events for c in (e.get_function_calls() or []) if c.name == _CONFIRM]
    return calls[-1] if calls else None


async def start(*, run_id: str, **_) -> dict:
    runner = _runner()
    await runner.session_service.create_session(app_name="poi", user_id="poi", session_id=run_id)
    request = _confirmation(await run_to_end(runner, run_id, user_text(TASK)))
    if request is None:
        return {"stop": "no_pause"}
    pending = request.args.get("originalFunctionCall", {}).get("args", {})
    return {"hold": True, "paused": True, "backend": BACKEND, "pending_digest": digest(pending)}


async def resume(*, run_id: str, approved: bool, **_) -> dict:
    from google.genai import types

    runner = _runner()
    session = await runner.session_service.get_session(app_name="poi", user_id="poi", session_id=run_id)
    request = _confirmation(session.events)
    reply = types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
        id=request.id, name=_CONFIRM, response={"confirmed": approved}))])
    await run_to_end(runner, run_id, reply)
    return {"stop": "final_answer"}
