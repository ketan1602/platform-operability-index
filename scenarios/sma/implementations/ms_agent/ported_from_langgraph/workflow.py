"""SMA on AutoGen — ported from LangGraph. Minimal changes from the LangGraph source.

LangGraph original: _delegate() wraps each specialist as a StructuredTool.
AutoGen port:       _delegate() wraps each specialist as an AgentTool.
Changed: framework imports, async def, chat_model→chat_client,
         create_react_agent→AssistantAgent, StructuredTool→AgentTool, .invoke()→.run()
"""
from __future__ import annotations
import os

from harness.frameworks.autogen_llm import chat_client
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


def _delegate(name: str, client):
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.tools import AgentTool

    agent = AssistantAgent(
        name, model_client=client,
        tools=[TOOLS_BY_SPECIALIST[name]],
        description=SPECIALIST_DESCRIPTIONS[name],
        system_message=SPECIALIST_INSTRUCTIONS[name],
        reflect_on_tool_use=True,
    )
    return AgentTool(agent, return_value_as_last_message=True)


async def run(**_) -> dict:
    from autogen_agentchat.agents import AssistantAgent

    client = chat_client()
    supervisor = AssistantAgent(
        SUPERVISOR, model_client=client,
        system_message=SUPERVISOR_INSTRUCTIONS,
        tools=[_delegate(n, client) for n in SPECIALISTS],
        max_tool_iterations=len(SPECIALISTS) + 1,
        reflect_on_tool_use=True,
    )
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    _termination = (MaxMessageTermination(max_messages=int(os.environ.get("AGENT_MAX_TURNS", "50")))
                    | TextMentionTermination("TERMINATE"))
    _team = RoundRobinGroupChat([supervisor], termination_condition=_termination)
    result = await _team.run(task=TASK)
    return {"stop": "final_answer", "answer": str(result.messages[-1].content)}
