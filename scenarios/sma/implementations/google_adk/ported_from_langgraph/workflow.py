"""SMA on Google ADK — ported from LangGraph. Minimal changes from the LangGraph source.

LangGraph original: _delegate() wraps each specialist as a StructuredTool.
ADK port:           _delegate() wraps each specialist LlmAgent as an AgentTool.
Changed: framework imports, async def, chat_model→llm(),
         create_react_agent→LlmAgent, StructuredTool→AgentTool,
         .invoke()→runner+run_to_end, prompt→instruction
"""
from __future__ import annotations
import os

from harness.frameworks.adk_llm import llm, run_to_end, user_text
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


def _delegate(name: str, model):
    from google.adk.agents import LlmAgent
    from google.adk.tools.agent_tool import AgentTool

    agent = LlmAgent(
        name=name, model=model,
        instruction=SPECIALIST_INSTRUCTIONS[name],
        description=SPECIALIST_DESCRIPTIONS[name],
        tools=[TOOLS_BY_SPECIALIST[name]],
    )
    return AgentTool(agent=agent)


async def run(**_) -> dict:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner

    model = llm()
    supervisor = LlmAgent(
        name=SUPERVISOR, model=model,
        instruction=SUPERVISOR_INSTRUCTIONS,
        tools=[_delegate(n, model) for n in SPECIALISTS],
    )
    runner = InMemoryRunner(agent=supervisor, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    from google.adk.agents.run_config import RunConfig
    _run_config = RunConfig(max_llm_calls=int(os.environ.get("AGENT_MAX_LLM_CALLS", "50")))
    events = await run_to_end(runner, session.id, user_text(TASK), run_config=_run_config)
    final = [e for e in events if e.is_final_response() and e.content and e.content.parts]
    answer = final[-1].content.parts[0].text if final else ""
    return {"stop": "final_answer", "answer": answer or ""}
