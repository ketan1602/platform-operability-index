"""SMA on LangGraph — ported from AutoGen. Minimal changes from the AutoGen source.

AutoGen original: flat run() with AssistantAgent specialists wrapped as AgentTools.
LangGraph port:   _delegate() helper wraps specialists as StructuredTools.
Changed: framework imports, sync def, chat_client→chat_model,
         AssistantAgent→create_react_agent, AgentTool→StructuredTool.from_function,
         system_message→prompt, supervisor.run(task=TASK)→supervisor.invoke,
         result.messages[-1].content→out["messages"][-1].content,
         _delegate helper introduced to mirror LangGraph idiom,
         removed max_tool_iterations and reflect_on_tool_use
"""
from __future__ import annotations
import os

from harness.frameworks.langgraph_llm import chat_model
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


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
    _max_turns = int(os.environ.get("AGENT_MAX_TURNS", "50"))
    out = supervisor.invoke({"messages": [("user", TASK)]}, config={"recursion_limit": _max_turns})
    return {"stop": "final_answer", "answer": out["messages"][-1].content}
