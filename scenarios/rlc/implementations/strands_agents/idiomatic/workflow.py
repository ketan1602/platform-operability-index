"""RLC on Strands: Agent event loop; the limit is the per-call limits={"turns": N}."""
from __future__ import annotations

from harness.frameworks.strands_llm import model
from scenarios.rlc.shared.tools import AGENT_NAME, INSTRUCTIONS, TASK, fetch_quarterly_report


def run(*, limit: int | None = None, **_) -> dict:
    from strands import Agent, tool

    agent = Agent(name=AGENT_NAME, model=model(), system_prompt=INSTRUCTIONS,
                  tools=[tool(fetch_quarterly_report)], callback_handler=None)
    extra = {} if limit is None else {"limits": {"turns": limit}}
    result = agent(TASK, **extra)
    if str(result.stop_reason).startswith("limit_"):
        return {"stop": "framework_limit", "signal": str(result.stop_reason), "structured": True}
    return {"stop": "final_answer", "signal": None, "structured": False}
