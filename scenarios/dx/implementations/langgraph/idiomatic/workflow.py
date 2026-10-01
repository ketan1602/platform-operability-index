"""DX on LangGraph — deliberately broken variants for error-clarity scoring.

mistake=A: tool returns int instead of str.
mistake=B: tool missing required `city` argument.
mistake=C: LLM client initialised with a malformed base_url.
"""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, broken_missing_arg, broken_noop, broken_return_type,
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


_DISPATCH = {"A": _mistake_a, "B": _mistake_b, "C": _mistake_c}


def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return fn()
