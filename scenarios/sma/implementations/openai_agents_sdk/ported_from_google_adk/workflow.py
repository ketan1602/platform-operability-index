"""SMA on OpenAI Agents SDK — ported from Google ADK. Minimal changes from the Google ADK source.

Google ADK original: async run() with LlmAgent specialists wrapped as AgentTools via InMemoryRunner.
OpenAI SDK port:    async run() with Agent specialists wrapped via Agent.as_tool.
Changed: framework imports, llm()→model(),
         LlmAgent→Agent, instruction→instructions,
         tools=[TOOLS_BY_SPECIALIST[n]]→function_tool(TOOLS_BY_SPECIALIST[n]),
         AgentTool(agent=a)→specialist.as_tool(tool_name, tool_description),
         InMemoryRunner/run_to_end/session→Runner.run(supervisor, TASK),
         final answer→result.final_output
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
    specialists = [
        Agent(name=n, instructions=SPECIALIST_INSTRUCTIONS[n], model=m,
              tools=[function_tool(TOOLS_BY_SPECIALIST[n])]
              ).as_tool(tool_name=n, tool_description=SPECIALIST_DESCRIPTIONS[n])
        for n in SPECIALISTS
    ]
    supervisor = Agent(name=SUPERVISOR, instructions=SUPERVISOR_INSTRUCTIONS, model=m, tools=specialists)
    _max_turns = int(os.environ.get("AGENT_MAX_TURNS", "50"))
    result = await Runner.run(supervisor, TASK, max_turns=_max_turns)
    return {"stop": "final_answer", "answer": str(result.final_output)}
