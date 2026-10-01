"""SMA on LangGraph: prebuilt ReAct supervisor whose tools invoke specialist ReAct agents."""
from __future__ import annotations

from harness.frameworks.langgraph_llm import chat_model
from scenarios.sma.shared.tools import (SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
                                        SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST)


def _delegate(name: str, llm):
    from langchain_core.tools import StructuredTool, tool
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(llm, [tool(TOOLS_BY_SPECIALIST[name])],
                               prompt=SPECIALIST_INSTRUCTIONS[name], name=name)

    def call(customer_id: str) -> str:
        return agent.invoke({"messages": [("user", customer_id)]})["messages"][-1].content

    return StructuredTool.from_function(call, name=name, description=SPECIALIST_DESCRIPTIONS[name])


def run(**_) -> dict:
    from langgraph.prebuilt import create_react_agent

    llm = chat_model()
    supervisor = create_react_agent(llm, [_delegate(n, llm) for n in SPECIALISTS],
                                    prompt=SUPERVISOR_INSTRUCTIONS, name=SUPERVISOR)
    out = supervisor.invoke({"messages": [("user", TASK)]})
    return {"stop": "final_answer", "answer": out["messages"][-1].content}
