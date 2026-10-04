"""SMA on OpenAI Agents SDK — ported from AutoGen. Minimal changes from the AutoGen source.

AutoGen original: flat run() with AssistantAgent specialists wrapped as AgentTools.
OpenAI SDK port:  flat run() with Agent specialists wrapped via Agent.as_tool.
Changed: framework imports, chat_client→model(),
         AssistantAgent→Agent, tools=[TOOLS_BY_SPECIALIST[n]]→function_tool,
         AgentTool(a, return_value_as_last_message=True)→Agent.as_tool,
         system_message→instructions, supervisor.run(task=TASK)→Runner.run(supervisor, TASK),
         result.messages[-1].content→result.final_output,
         removed max_tool_iterations and reflect_on_tool_use
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
