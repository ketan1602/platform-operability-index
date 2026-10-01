"""RLC on the OpenAI Agents SDK: Runner loop; the limit is max_turns."""
from __future__ import annotations

from harness.frameworks.openai_agents_llm import model
from scenarios.rlc.shared.tools import AGENT_NAME, INSTRUCTIONS, TASK, fetch_quarterly_report


async def run(*, limit: int | None = None, **_) -> dict:
    from agents import Agent, Runner, function_tool
    from agents.exceptions import MaxTurnsExceeded

    agent = Agent(name=AGENT_NAME, instructions=INSTRUCTIONS, model=model(),
                  tools=[function_tool(fetch_quarterly_report)])
    extra = {} if limit is None else {"max_turns": limit}
    try:
        await Runner.run(agent, TASK, **extra)
    except MaxTurnsExceeded:
        return {"stop": "framework_limit", "signal": "MaxTurnsExceeded", "structured": True}
    return {"stop": "final_answer", "signal": None, "structured": False}
