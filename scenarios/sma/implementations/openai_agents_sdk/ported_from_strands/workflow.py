"""SMA on OpenAI Agents SDK — ported from Strands. Minimal changes from the Strands source.

Strands original: flat run() with Agent specialists wrapped via Agent.as_tool.
OpenAI SDK port:  flat run() with Agent specialists wrapped via Agent.as_tool.
Changed: framework imports, async def, model()→model() (openai_agents_llm),
         Agent (Strands)→Agent (OpenAI), tool→function_tool, system_prompt→instructions,
         Agent.as_tool(name,description)→Agent.as_tool(tool_name,tool_description),
         supervisor(TASK)→Runner.run(supervisor, TASK), str(result)→str(result.final_output),
         removed callback_handler=None
"""
from __future__ import annotations
import os

from harness.frameworks.openai_agents_llm import model
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


async def run(**_) -> dict:
    from agents import Agent, Runner, function_tool

    m = model()
    tools = [
        Agent(name=n, instructions=SPECIALIST_INSTRUCTIONS[n], model=m,
              tools=[function_tool(TOOLS_BY_SPECIALIST[n])]
              ).as_tool(tool_name=n, tool_description=SPECIALIST_DESCRIPTIONS[n])
        for n in SPECIALISTS
    ]
    supervisor = Agent(name=SUPERVISOR, instructions=SUPERVISOR_INSTRUCTIONS, model=m, tools=tools)
    _max_turns = int(os.environ.get("AGENT_MAX_TURNS", "50"))
    result = await Runner.run(supervisor, TASK, max_turns=_max_turns)
    return {"stop": "final_answer", "answer": str(result.final_output)}
