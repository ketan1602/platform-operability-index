"""PORT on AutoGen: sub_test='switch' (P6 switching cost) and 'isolation' (P2/SMA)."""
from __future__ import annotations
import json

from harness.frameworks.autogen_llm import chat_client
from scenarios.port.shared.tools import (
    TASK, TASK_FETCH_TPL, analyse, draft_report, fetch_data, search,
)


def _json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


async def _run_switch() -> dict:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_core.tools import FunctionTool

    tools = [
        FunctionTool(search, description=search.__doc__ or "Search"),
        FunctionTool(analyse, description=analyse.__doc__ or "Analyse"),
        FunctionTool(draft_report, description=draft_report.__doc__ or "Draft report"),
    ]
    agent = AssistantAgent("port_agent", model_client=chat_client(),
                           tools=tools, reflect_on_tool_use=True)
    result = await agent.run(task=TASK)
    return {"stop": "final_answer", "sub_test": "switch",
            "answer": str(result.messages[-1].content),
            "state_json_safe": _json_safe(result)}


async def _run_tools_raw() -> dict:
    from autogen_agentchat.agents import AssistantAgent

    agent = AssistantAgent("port_raw", model_client=chat_client(),
                           tools=[search, analyse, draft_report], reflect_on_tool_use=True)
    result = await agent.run(task=TASK)
    return {"stop": "final_answer", "sub_test": "tools_raw",
            "answer": str(result.messages[-1].content)}


async def _run_isolation(run_id: str) -> dict:
    from autogen_agentchat.agents import AssistantAgent

    agent = AssistantAgent("port_agent", model_client=chat_client(),
                           tools=[fetch_data], reflect_on_tool_use=True)
    task = TASK_FETCH_TPL.format(run_id=run_id)
    result = await agent.run(task=task)
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
            "answer": str(result.messages[-1].content)}


async def _run_context_port() -> dict:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_core.tools import FunctionTool
    from scenarios.port.shared.history import CONTEXT_KEYWORD, FOLLOWUP, HISTORY

    parts = []
    for m in HISTORY:
        if m.get("content"):
            parts.append(f"{m['role'].upper()}: {m['content']}")
        elif m.get("tool_calls"):
            for tc in m["tool_calls"]:
                parts.append(f"ASSISTANT called {tc['function']['name']}")
    task = f"Prior conversation:\n" + "\n".join(parts) + f"\n\nContinue: {FOLLOWUP}"

    agent = AssistantAgent("port_agent", model_client=chat_client(),
                           tools=[FunctionTool(search, description=search.__doc__ or "Search")],
                           reflect_on_tool_use=True)
    result = await agent.run(task=task)
    answer = str(result.messages[-1].content)
    return {"stop": "final_answer", "sub_test": "context_port",
            "context_portable": CONTEXT_KEYWORD in answer,
            "injection": "prompt_fallback", "answer": answer}


async def run(*, sub_test: str = "switch", run_id: str = "", **_) -> dict:
    if sub_test == "tools_raw":
        return await _run_tools_raw()
    if sub_test == "isolation":
        return await _run_isolation(run_id)
    if sub_test == "context_port":
        return await _run_context_port()
    return await _run_switch()
