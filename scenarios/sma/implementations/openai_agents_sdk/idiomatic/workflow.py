"""SMA on the OpenAI Agents SDK: manager agent using specialists via Agent.as_tool."""
from __future__ import annotations

from harness.frameworks.openai_agents_llm import model
from scenarios.sma.shared.tools import (SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
                                        SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST)


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
    result = await Runner.run(supervisor, TASK)
    return {"stop": "final_answer", "answer": str(result.final_output)}
