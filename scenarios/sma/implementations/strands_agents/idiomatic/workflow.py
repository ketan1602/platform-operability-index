"""SMA on Strands: orchestrator Agent with specialist Agents exposed via Agent.as_tool."""
from __future__ import annotations

from harness.frameworks.strands_llm import model
from scenarios.sma.shared.tools import (SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
                                        SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST)


def run(**_) -> dict:
    from strands import Agent, tool

    m = model()
    tools = [
        Agent(name=n, description=SPECIALIST_DESCRIPTIONS[n], model=m, system_prompt=SPECIALIST_INSTRUCTIONS[n],
              tools=[tool(TOOLS_BY_SPECIALIST[n])], callback_handler=None
              ).as_tool(name=n, description=SPECIALIST_DESCRIPTIONS[n])
        for n in SPECIALISTS
    ]
    supervisor = Agent(name=SUPERVISOR, model=m, system_prompt=SUPERVISOR_INSTRUCTIONS,
                       tools=tools, callback_handler=None)
    result = supervisor(TASK)
    return {"stop": "final_answer", "answer": str(result)}
