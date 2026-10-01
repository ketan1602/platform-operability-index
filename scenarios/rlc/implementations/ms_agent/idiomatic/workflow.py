"""RLC on AutoGen: AssistantAgent; the limit is max_tool_iterations."""
from __future__ import annotations

from harness.frameworks.autogen_llm import chat_client
from scenarios.rlc.shared.tools import AGENT_NAME, INSTRUCTIONS, TASK, fetch_quarterly_report


async def run(*, limit: int | None = None, **_) -> dict:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.messages import ToolCallSummaryMessage

    extra = {} if limit is None else {"max_tool_iterations": limit}
    agent = AssistantAgent(AGENT_NAME, model_client=chat_client(), tools=[fetch_quarterly_report],
                           system_message=INSTRUCTIONS, **extra)
    result = await agent.run(task=TASK)
    # With reflection off, hitting the iteration cap ends on a tool-call summary, not text.
    if isinstance(result.messages[-1], ToolCallSummaryMessage):
        return {"stop": "framework_limit", "signal": "ToolCallSummaryMessage", "structured": True}
    return {"stop": "final_answer", "signal": None, "structured": False}
