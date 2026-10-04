"""PORT on Google ADK: sub_test='switch' (P6 switching cost) and 'isolation' (P2/SMA)."""
from __future__ import annotations
import json

from harness.frameworks.adk_llm import llm, run_to_end, user_text
from scenarios.port.shared.tools import (
    TASK, TASK_FETCH_TPL, analyse, draft_report, fetch_data, search,
)


def _json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


async def _run_agent(task: str, tools: list) -> tuple[str, bool]:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner

    agent = LlmAgent(name="port_agent", model=llm(), tools=tools)
    runner = InMemoryRunner(agent=agent, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    events = await run_to_end(runner, session.id, user_text(task))
    json_safe = _json_safe(events)
    final = [e for e in events if e.is_final_response() and e.content and e.content.parts]
    answer = final[-1].content.parts[0].text if final else ""
    return answer, json_safe


async def _run_tools_raw() -> dict:
    answer, _ = await _run_agent(TASK, [search, analyse, draft_report])
    return {"stop": "final_answer", "sub_test": "tools_raw", "answer": answer}


async def _run_context_port() -> dict:
    from scenarios.port.shared.history import CONTEXT_KEYWORD, FOLLOWUP, HISTORY

    parts = []
    for m in HISTORY:
        if m.get("content"):
            parts.append(f"{m['role'].upper()}: {m['content']}")
        elif m.get("tool_calls"):
            for tc in m["tool_calls"]:
                parts.append(f"ASSISTANT called {tc['function']['name']}")
    task = "Prior conversation:\n" + "\n".join(parts) + f"\n\nContinue: {FOLLOWUP}"
    answer, _ = await _run_agent(task, [search])
    return {"stop": "final_answer", "sub_test": "context_port",
            "context_portable": CONTEXT_KEYWORD in answer,
            "injection": "prompt_fallback", "answer": answer}


async def run(*, sub_test: str = "switch", run_id: str = "", **_) -> dict:
    if sub_test == "tools_raw":
        return await _run_tools_raw()
    if sub_test == "isolation":
        answer, json_safe = await _run_agent(
            TASK_FETCH_TPL.format(run_id=run_id), [fetch_data]
        )
        return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
                "answer": answer, "state_json_safe": json_safe}
    if sub_test == "context_port":
        return await _run_context_port()
    answer, json_safe = await _run_agent(TASK, [search, analyse, draft_report])
    return {"stop": "final_answer", "sub_test": "switch", "answer": answer,
            "state_json_safe": json_safe}
