"""SMA on AutoGen — ported from OpenAI Agents SDK. Minimal changes from the OpenAI SDK source.

OpenAI SDK original: flat run() with Agent specialists wrapped via Agent.as_tool.
AutoGen port:        flat run() with AssistantAgent specialists wrapped as AgentTools.
Changed: framework imports, model()→chat_client(),
         Agent→AssistantAgent, function_tool→TOOLS_BY_SPECIALIST (direct),
         instructions→system_message, Agent.as_tool→AgentTool(a, return_value_as_last_message=True),
         Runner.run(supervisor, TASK)→supervisor.run(task=TASK),
         result.final_output→result.messages[-1].content,
         added max_tool_iterations=len(SPECIALISTS)+1 and reflect_on_tool_use=True
"""
from __future__ import annotations
import os

from harness.frameworks.autogen_llm import chat_client
from scenarios.sma.shared.tools import (
    SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
    SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST,
)


async def run(**_) -> dict:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.tools import AgentTool

    client = chat_client()
    specialists = [
        AssistantAgent(n, model_client=client, tools=[TOOLS_BY_SPECIALIST[n]],
                       description=SPECIALIST_DESCRIPTIONS[n], system_message=SPECIALIST_INSTRUCTIONS[n],
                       reflect_on_tool_use=True)
        for n in SPECIALISTS
    ]
    supervisor = AssistantAgent(SUPERVISOR, model_client=client, system_message=SUPERVISOR_INSTRUCTIONS,
                                tools=[AgentTool(a, return_value_as_last_message=True) for a in specialists],
                                max_tool_iterations=len(SPECIALISTS) + 1, reflect_on_tool_use=True)
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    _termination = (MaxMessageTermination(max_messages=int(os.environ.get("AGENT_MAX_TURNS", "50")))
                    | TextMentionTermination("TERMINATE"))
    _team = RoundRobinGroupChat([supervisor], termination_condition=_termination)
    result = await _team.run(task=TASK)
    return {"stop": "final_answer", "answer": str(result.messages[-1].content)}
