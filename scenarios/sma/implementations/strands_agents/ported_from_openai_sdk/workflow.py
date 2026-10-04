"""SMA on Strands — ported from OpenAI Agents SDK. Minimal changes from the OpenAI SDK source.

OpenAI SDK original: flat run() with Agent specialists wrapped via Agent.as_tool.
Strands port:        flat run() with Agent (Strands) specialists wrapped via Agent.as_tool.
Changed: framework imports, sync def, model()→model() (strands_llm),
         Agent→Agent (Strands), function_tool→tool, instructions→system_prompt,
         Agent.as_tool(tool_name,tool_description)→Agent.as_tool(name,description),
         added callback_handler=None, Runner.run→supervisor(TASK), result.final_output→str(result)
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
