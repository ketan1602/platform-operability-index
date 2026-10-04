"""SMA on OpenAI Agents SDK — ported from LangGraph. Minimal changes from the LangGraph source.

LangGraph original: _delegate() wraps each specialist as a StructuredTool.
OpenAI SDK port:    _delegate() wraps each specialist Agent via Agent.as_tool.
Changed: framework imports, async def, chat_model→model(),
         create_react_agent→Agent, StructuredTool.from_function→Agent.as_tool,
         prompt→instructions, supervisor.invoke→Runner.run, result["messages"][-1].content→result.final_output
"""
from __future__ import annotations
import os

from harness.frameworks.openai_agents_llm import model
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


def _delegate(name: str, m):
    from agents import Agent, function_tool

    agent = Agent(name=name, instructions=SPECIALIST_INSTRUCTIONS[name], model=m,
                  tools=[function_tool(TOOLS_BY_SPECIALIST[name])])
    return agent.as_tool(tool_name=name, tool_description=SPECIALIST_DESCRIPTIONS[name])


async def run(**_) -> dict:
    from agents import Agent, Runner

    m = model()
    supervisor = Agent(name=SUPERVISOR, instructions=SUPERVISOR_INSTRUCTIONS, model=m,
                       tools=[_delegate(n, m) for n in SPECIALISTS])
    _max_turns = int(os.environ.get("AGENT_MAX_TURNS", "50"))
    result = await Runner.run(supervisor, TASK, max_turns=_max_turns)
    return {"stop": "final_answer", "answer": str(result.final_output)}
