"""SMA on AutoGen: supervisor AssistantAgent with specialist agents wrapped as AgentTools."""
from __future__ import annotations

from harness.frameworks.autogen_llm import chat_client
from scenarios.sma.shared.tools import (SPECIALIST_DESCRIPTIONS, SPECIALIST_INSTRUCTIONS, SPECIALISTS,
                                        SUPERVISOR, SUPERVISOR_INSTRUCTIONS, TASK, TOOLS_BY_SPECIALIST)


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
    # One delegation per specialist can take separate iterations; the default of 1 would stop early.
    supervisor = AssistantAgent(SUPERVISOR, model_client=client, system_message=SUPERVISOR_INSTRUCTIONS,
                                tools=[AgentTool(a, return_value_as_last_message=True) for a in specialists],
                                max_tool_iterations=len(SPECIALISTS) + 1, reflect_on_tool_use=True)
    result = await supervisor.run(task=TASK)
    return {"stop": "final_answer", "answer": str(result.messages[-1].content)}
