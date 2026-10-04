"""PORT on Strands: sub_test='switch' (P6 switching cost) and 'isolation' (P2/SMA)."""
from __future__ import annotations
import json

from harness.frameworks.strands_llm import model
from scenarios.port.shared.tools import (
    TASK, TASK_FETCH_TPL, analyse, draft_report, fetch_data, search,
)


def _json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


def _run_switch() -> dict:
    from strands import Agent, tool

    tools = [tool(search), tool(analyse), tool(draft_report)]
    agent = Agent(name="port_agent", model=model(), tools=tools, callback_handler=None)
    result = agent(TASK)
    return {"stop": "final_answer", "sub_test": "switch",
            "answer": str(result),
            "state_json_safe": _json_safe(result)}


def _run_tools_raw() -> dict:
    from strands import Agent

    try:
        agent = Agent(name="port_raw", model=model(), tools=[search, analyse, draft_report],
                      callback_handler=None)
        result = agent(TASK)
        answer = str(result)
    except Exception:
        answer = ""
    return {"stop": "final_answer", "sub_test": "tools_raw", "answer": answer}


def _run_isolation(run_id: str) -> dict:
    from strands import Agent, tool

    agent = Agent(name="port_agent", model=model(), tools=[tool(fetch_data)],
                  callback_handler=None)
    task = TASK_FETCH_TPL.format(run_id=run_id)
    result = agent(task)
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
            "answer": str(result)}


def _run_context_port() -> dict:
    from strands import Agent, tool
    from scenarios.port.shared.history import CONTEXT_KEYWORD, FOLLOWUP, HISTORY

    parts = []
    for m in HISTORY:
        if m.get("content"):
            parts.append(f"{m['role'].upper()}: {m['content']}")
        elif m.get("tool_calls"):
            for tc in m["tool_calls"]:
                parts.append(f"ASSISTANT called {tc['function']['name']}")
    task = "Prior conversation:\n" + "\n".join(parts) + f"\n\nContinue: {FOLLOWUP}"

    agent = Agent(name="port_agent", model=model(), tools=[tool(search)],
                  callback_handler=None)
    result = agent(task)
    answer = str(result)
    return {"stop": "final_answer", "sub_test": "context_port",
            "context_portable": CONTEXT_KEYWORD in answer,
            "injection": "prompt_fallback", "answer": answer}


def run(*, sub_test: str = "switch", run_id: str = "", **_) -> dict:
    if sub_test == "tools_raw":
        return _run_tools_raw()
    if sub_test == "isolation":
        return _run_isolation(run_id)
    if sub_test == "context_port":
        return _run_context_port()
    return _run_switch()
