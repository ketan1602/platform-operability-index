"""SMA on Strands — ported from LangGraph. Minimal changes from the LangGraph source.

LangGraph original: _delegate() wraps each specialist as a StructuredTool.
Strands port:       _delegate() wraps each specialist Agent via Agent.as_tool.
Changed: framework imports, chat_model→model() (strands_llm),
         create_react_agent→Agent (Strands), StructuredTool.from_function→Agent.as_tool,
         prompt→system_prompt, supervisor.invoke→supervisor(TASK), str(result),
         added callback_handler=None, run stays sync
"""
from __future__ import annotations
import os

from harness.frameworks.strands_llm import model
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


def _delegate(name: str, m):
    from strands import Agent, tool

    agent = Agent(name=name, description=SPECIALIST_DESCRIPTIONS[name], model=m,
                  system_prompt=SPECIALIST_INSTRUCTIONS[name],
                  tools=[tool(TOOLS_BY_SPECIALIST[name])], callback_handler=None)
    return agent.as_tool(name=name, description=SPECIALIST_DESCRIPTIONS[name])


def run(**_) -> dict:
    from strands import Agent

    m = model()
    supervisor = Agent(name=SUPERVISOR, model=m, system_prompt=SUPERVISOR_INSTRUCTIONS,
                       tools=[_delegate(n, m) for n in SPECIALISTS], callback_handler=None)
    _max_iters = int(os.environ.get("AGENT_MAX_TURNS", "50"))
    result = supervisor(TASK, max_iterations=_max_iters)
    return {"stop": "final_answer", "answer": str(result)}
