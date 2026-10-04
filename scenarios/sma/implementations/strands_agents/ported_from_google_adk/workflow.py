"""SMA on Strands — ported from Google ADK. Minimal changes from the Google ADK source.

Google ADK original: async run() with LlmAgent specialists wrapped as AgentTools via InMemoryRunner.
Strands port:       sync run() with Agent specialists wrapped via Agent.as_tool.
Changed: framework imports, async→sync, llm()→model() (strands_llm),
         LlmAgent→Agent (Strands), instruction→system_prompt,
         tools=[TOOLS_BY_SPECIALIST[n]]→tool(TOOLS_BY_SPECIALIST[n]),
         AgentTool(agent=a)→Agent.as_tool(name, description), added callback_handler=None,
         InMemoryRunner/run_to_end/session→supervisor(TASK),
         final answer→str(result)
"""
from __future__ import annotations
import os

from harness.frameworks.strands_llm import model
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


def run(**_) -> dict:
    from strands import Agent, tool

    m = model()
    tools = [
        Agent(name=n, description=SPECIALIST_DESCRIPTIONS[n], model=m,
              system_prompt=SPECIALIST_INSTRUCTIONS[n],
              tools=[tool(TOOLS_BY_SPECIALIST[n])], callback_handler=None
              ).as_tool(name=n, description=SPECIALIST_DESCRIPTIONS[n])
        for n in SPECIALISTS
    ]
    supervisor = Agent(name=SUPERVISOR, model=m, system_prompt=SUPERVISOR_INSTRUCTIONS,
                       tools=tools, callback_handler=None)
    _max_iters = int(os.environ.get("AGENT_MAX_TURNS", "50"))
    result = supervisor(TASK, max_iterations=_max_iters)
    return {"stop": "final_answer", "answer": str(result)}
