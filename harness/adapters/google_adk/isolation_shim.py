"""isolation_shim — Google ADK F4 runaway-loop containment.

Lines between poi:custom markers are operator-written code required to add
loop limiting. ADK has no default limit; RunConfig(max_llm_calls=N) must be
constructed and passed on every invocation.
"""
from __future__ import annotations
import os
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# poi:custom-begin
_max_calls = int(os.environ.get("AGENT_MAX_LLM_CALLS", "50"))
_run_config = RunConfig(max_llm_calls=_max_calls)
_session_svc = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=_APP_NAME, session_service=_session_svc)
session = await _session_svc.create_session(
    app_name=_APP_NAME, user_id="user", session_id=session_id
)
content = types.Content(role="user", parts=[types.Part(text=prompt)])
events = runner.run_async(
    session_id=session.id, user_id="user", new_message=content, run_config=_run_config
)
# poi:custom-end
