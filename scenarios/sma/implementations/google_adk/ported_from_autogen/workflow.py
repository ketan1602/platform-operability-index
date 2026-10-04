"""SMA on Google ADK — ported from AutoGen. Minimal changes from the AutoGen source.

AutoGen original: flat run() with AssistantAgent specialists wrapped as AgentTools.
ADK port:         flat run() with LlmAgent specialists wrapped as AgentTools.
Changed: framework imports, chat_client→llm(),
         AssistantAgent→LlmAgent, system_message→instruction,
         AgentTool(a, return_value_as_last_message=True)→AgentTool(agent=a),
         supervisor.run(task=TASK)→InMemoryRunner+run_to_end+event extraction,
         result.messages[-1].content→final event text,
         removed max_tool_iterations and reflect_on_tool_use
"""
from __future__ import annotations
import os

from harness.frameworks.adk_llm import llm, run_to_end, user_text
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


async def run(**_) -> dict:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.adk.tools.agent_tool import AgentTool

    model = llm()
    specialists = [
        LlmAgent(name=n, model=model, instruction=SPECIALIST_INSTRUCTIONS[n],
                 description=SPECIALIST_DESCRIPTIONS[n], tools=[TOOLS_BY_SPECIALIST[n]])
        for n in SPECIALISTS
    ]
    supervisor = LlmAgent(name=SUPERVISOR, model=model, instruction=SUPERVISOR_INSTRUCTIONS,
                          tools=[AgentTool(agent=a) for a in specialists])
    runner = InMemoryRunner(agent=supervisor, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    from google.adk.agents.run_config import RunConfig
    _run_config = RunConfig(max_llm_calls=int(os.environ.get("AGENT_MAX_LLM_CALLS", "50")))
    events = await run_to_end(runner, session.id, user_text(TASK), run_config=_run_config)
    final = [e for e in events if e.is_final_response() and e.content and e.content.parts]
    answer = final[-1].content.parts[0].text if final else ""
    return {"stop": "final_answer", "answer": answer or ""}
