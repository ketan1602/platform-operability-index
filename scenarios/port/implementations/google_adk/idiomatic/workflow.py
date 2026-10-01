"""PORT on Google ADK: sub-tests 2 (isolation) and 3 (tool extensibility)."""
from __future__ import annotations

from harness.frameworks.adk_llm import llm, run_to_end, user_text
from scenarios.port.shared.tools import (
    AGENT_NAME, TASK_FETCH_TPL, TASK_WEATHER, fetch_data, get_weather,
)


async def _run_agent(task: str, tool_fn) -> str:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner

    agent = LlmAgent(name=AGENT_NAME, model=llm(), tools=[tool_fn])
    runner = InMemoryRunner(agent=agent, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    events = await run_to_end(runner, session.id, user_text(task))
    final = [e for e in events if e.is_final_response() and e.content and e.content.parts]
    return final[-1].content.parts[0].text if final else ""


async def run(*, sub_test: str = "tool_ext", run_id: str = "", **_) -> dict:
    if sub_test == "isolation":
        answer = await _run_agent(TASK_FETCH_TPL.format(run_id=run_id), fetch_data)
        return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id, "answer": answer}
    answer = await _run_agent(TASK_WEATHER, get_weather)
    return {"stop": "final_answer", "sub_test": "tool_ext", "answer": answer}
