"""DX on LangGraph — deliberately broken variants for error-clarity scoring.

mistake=A: tool returns int instead of str.
mistake=B: tool missing required `city` argument.
mistake=C: LLM client initialised with a malformed base_url.
"""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, TASK_SMOKE, broken_missing_arg, broken_noop, broken_return_type,
    broken_return_none, broken_wrong_annotation, greet,
)


def _react_agent(llm, tools, task: str) -> dict:
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(llm, [tool(t) for t in tools])
    out = agent.invoke({"messages": [("user", task)]})
    return {"stop": "final_answer", "answer": out["messages"][-1].content}


def _mistake_a() -> dict:
    from harness.frameworks.langgraph_llm import chat_model
    return _react_agent(chat_model(), [broken_return_type], TASK_WEATHER)


def _mistake_b() -> dict:
    from harness.frameworks.langgraph_llm import chat_model
    return _react_agent(chat_model(), [broken_missing_arg], TASK_WEATHER)


def _mistake_c() -> dict:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o", base_url="not-a-valid-url", api_key="dummy")
    return _react_agent(llm, [broken_noop], TASK_WEATHER)


def _mistake_smoke() -> dict:
    from harness.frameworks.langgraph_llm import chat_model
    return _react_agent(chat_model(), [greet], TASK_SMOKE)


def _mistake_middleware() -> dict:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent
    from harness.frameworks.langgraph_llm import chat_model
    from harness.shared import ledger

    class _MWHandler(BaseCallbackHandler):
        def on_tool_start(self, serialized, input_str, **kwargs):
            ledger.record("middleware_fired")

    agent = create_react_agent(chat_model(), [tool(broken_noop)])
    agent.invoke(
        {"messages": [("user", TASK_WEATHER)]},
        config={"callbacks": [_MWHandler()]},
    )
    return {"stop": "final_answer", "middleware": True}


def _mistake_d() -> dict:
    from harness.frameworks.langgraph_llm import chat_model
    return _react_agent(chat_model(), [broken_return_none], TASK_WEATHER)


def _mistake_e() -> dict:
    from harness.frameworks.langgraph_llm import chat_model
    return _react_agent(chat_model(), [broken_wrong_annotation], TASK_WEATHER)


def _mistake_hitl() -> dict:
    from typing import TypedDict
    from langgraph.graph import StateGraph, START, END
    from harness.shared import ledger
    import os, time
    # poi:custom-begin
    approval = os.environ.get("POI_HITL_APPROVAL", "")

    class S(TypedDict):
        result: str

    def work(s: S) -> S:
        return {"result": "Weather: 72F"}

    def gate(s: S) -> S:
        ledger.record("hitl_hold")
        deadline = time.time() + 60
        while time.time() < deadline:
            if approval and os.path.exists(approval):
                break
            time.sleep(0.5)
        ledger.record("hitl_completed")
        return s

    g = StateGraph(S)
    g.add_node("work", work); g.add_node("gate", gate)
    g.add_edge(START, "work"); g.add_edge("work", "gate"); g.add_edge("gate", END)
    out = g.compile().invoke({"result": ""})
    return {"stop": "final_answer", "answer": out["result"]}
    # poi:custom-end


def _escape_hatch() -> dict:
    probes = 0
    try:
        from langchain_openai import ChatOpenAI
        ChatOpenAI(model="gpt-4o", base_url="http://localhost:11434/v1", api_key="dummy")
        probes += 1
    except Exception:
        pass
    import os
    if os.environ.get("POI_LLM_MODEL"):
        probes += 1
    # LANGCHAIN_TRACING_V2=false disables all tracing — always supported
    probes += 1
    return {"stop": "final_answer", "probes_passed": probes}


_DISPATCH = {
    "A": _mistake_a, "B": _mistake_b, "C": _mistake_c,
    "D": _mistake_d, "E": _mistake_e,
    "SMOKE": _mistake_smoke, "MIDDLEWARE": _mistake_middleware,
    "ESCAPE_HATCH": _escape_hatch, "HITL": _mistake_hitl,
}


def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return fn()
