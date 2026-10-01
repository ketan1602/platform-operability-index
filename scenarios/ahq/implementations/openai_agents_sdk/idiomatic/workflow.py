"""AHQ on the OpenAI Agents SDK: needs_approval tool, RunState serialisation.

RunState serialises natively, but sessions don't persist pending approvals, so the
state string goes to Postgres through the shared custom store — counted as tax.
"""
from __future__ import annotations
import json

from harness.frameworks.openai_agents_llm import model
from scenarios.ahq.shared import state_store
from scenarios.ahq.shared.tools import (AGENT_NAME, INSTRUCTIONS, TASK, apply_plan_change, digest,
                                        lookup_account)

CUSTOM_STORE = True
BACKEND = "postgres (custom store for RunState)"


def _agent():
    from agents import Agent, function_tool

    return Agent(name=AGENT_NAME, instructions=INSTRUCTIONS, model=model(),
                 tools=[function_tool(lookup_account), function_tool(apply_plan_change, needs_approval=True)])


async def start(*, run_id: str, **_) -> dict:
    from agents import Runner

    result = await Runner.run(_agent(), TASK)
    if not result.interruptions:
        return {"stop": "no_pause"}
    pending = json.loads(result.interruptions[0].raw_item.arguments or "{}")
    # poi:custom-begin
    state_store.save(run_id, result.to_state().to_string())
    # poi:custom-end
    return {"hold": True, "paused": True, "backend": BACKEND, "pending_digest": digest(pending)}


async def resume(*, run_id: str, approved: bool, **_) -> dict:
    from agents import RunState, Runner

    agent = _agent()
    # poi:custom-begin
    state = await RunState.from_string(agent, state_store.load(run_id))
    # poi:custom-end
    for item in state.get_interruptions():
        state.approve(item) if approved else state.reject(item)
    await Runner.run(agent, state)
    return {"stop": "final_answer"}
