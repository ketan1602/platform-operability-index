"""AHQ on AutoGen: the agent hands off to the approver (HandoffTermination).

AutoGen serialises team state (save_state) but has no durable store, so the state
goes to Postgres through the shared custom store — counted as operability tax.
"""
from __future__ import annotations
import json

from harness.frameworks.autogen_llm import chat_client
from scenarios.ahq.shared import state_store
from scenarios.ahq.shared.tools import AGENT_NAME, INSTRUCTIONS, TASK, apply_plan_change, lookup_account

CUSTOM_STORE = True
BACKEND = "postgres (custom store for save_state)"
_GATE = ("AutoGen has no per-tool approval: after lookup_account, hand off to 'approver' stating "
         "the exact change. Only after you receive APPROVED, call apply_plan_change, then reply DONE.")


def _team():
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.conditions import HandoffTermination, MaxMessageTermination, TextMentionTermination
    from autogen_agentchat.teams import RoundRobinGroupChat

    agent = AssistantAgent(AGENT_NAME, model_client=chat_client(), handoffs=["approver"],
                           tools=[lookup_account, apply_plan_change],
                           system_message=INSTRUCTIONS + " " + _GATE)
    stop = HandoffTermination("approver") | TextMentionTermination("DONE") | MaxMessageTermination(20)
    return RoundRobinGroupChat([agent], termination_condition=stop)


async def start(*, run_id: str, **_) -> dict:
    from autogen_agentchat.messages import HandoffMessage

    team = _team()
    result = await team.run(task=TASK)
    if not any(isinstance(m, HandoffMessage) for m in result.messages):
        return {"stop": "no_pause"}
    # poi:custom-begin
    state_store.save(run_id, json.dumps(await team.save_state()))
    # poi:custom-end
    return {"hold": True, "paused": True, "backend": BACKEND, "pending_digest": None}


async def resume(*, run_id: str, approved: bool, **_) -> dict:
    team = _team()
    # poi:custom-begin
    await team.load_state(json.loads(state_store.load(run_id)))
    # poi:custom-end
    await team.run(task="APPROVED" if approved else "REJECTED")
    return {"stop": "final_answer"}
