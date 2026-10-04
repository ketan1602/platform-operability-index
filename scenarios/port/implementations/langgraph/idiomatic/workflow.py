"""PORT on LangGraph: sub_test='switch' (P6 switching cost) and 'isolation' (P2/SMA)."""
from __future__ import annotations
import json

from harness.frameworks.langgraph_llm import chat_model
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
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    tools = [tool(search), tool(analyse), tool(draft_report)]
    agent = create_react_agent(chat_model(), tools)
    out = agent.invoke({"messages": [("user", TASK)]})
    return {"stop": "final_answer", "sub_test": "switch",
            "answer": out["messages"][-1].content,
            "state_json_safe": _json_safe(out)}


def _run_tools_raw() -> dict:
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(chat_model(), [search, analyse, draft_report])
    out = agent.invoke({"messages": [("user", TASK)]})
    return {"stop": "final_answer", "sub_test": "tools_raw",
            "answer": out["messages"][-1].content}


def _run_isolation(run_id: str) -> dict:
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(chat_model(), [tool(fetch_data)])
    task = TASK_FETCH_TPL.format(run_id=run_id)
    out = agent.invoke({"messages": [("user", task)]})
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
            "answer": out["messages"][-1].content}


def _run_context_port() -> dict:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent
    from scenarios.port.shared.history import CONTEXT_KEYWORD, FOLLOWUP, HISTORY

    def _conv(msg: dict):
        if msg["role"] == "user":
            return HumanMessage(content=msg["content"])
        if msg["role"] == "tool":
            return ToolMessage(content=msg["content"], tool_call_id=msg["tool_call_id"])
        tc = [{"name": c["function"]["name"],
               "args": json.loads(c["function"]["arguments"]),
               "id": c["id"], "type": "tool_call"} for c in (msg.get("tool_calls") or [])]
        return AIMessage(content=msg.get("content") or "", tool_calls=tc)

    messages = [_conv(m) for m in HISTORY] + [HumanMessage(content=FOLLOWUP)]
    agent = create_react_agent(chat_model(), [tool(search)])
    out = agent.invoke({"messages": messages})
    answer = out["messages"][-1].content
    return {"stop": "final_answer", "sub_test": "context_port",
            "context_portable": CONTEXT_KEYWORD in answer,
            "injection": "native", "answer": answer}


def run(*, sub_test: str = "switch", run_id: str = "", **_) -> dict:
    if sub_test == "tools_raw":
        return _run_tools_raw()
    if sub_test == "isolation":
        return _run_isolation(run_id)
    if sub_test == "context_port":
        return _run_context_port()
    return _run_switch()
