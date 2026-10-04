"""SMA on Strands — ported from AutoGen. Minimal changes from the AutoGen source.

AutoGen original: flat run() with AssistantAgent specialists wrapped as AgentTools.
Strands port:     flat run() with Agent specialists wrapped via Agent.as_tool.
Changed: framework imports, sync def, chat_client→model() (strands_llm),
         AssistantAgent→Agent (Strands), system_message→system_prompt,
         tools=[TOOLS_BY_SPECIALIST[n]]→tool(TOOLS_BY_SPECIALIST[n]),
         AgentTool→Agent.as_tool, added callback_handler=None,
         supervisor.run(task=TASK)→supervisor(TASK), str(result.messages[-1].content)→str(result),
         removed max_tool_iterations and reflect_on_tool_use
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
