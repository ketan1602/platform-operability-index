"""TCW fixed workflow — AutoGen AgentChat with 5 specialist agents.

Each agent owns one TCW step; they execute sequentially via RoundRobinGroupChat.
DRY_RUN=true returns a canned result without starting any AutoGen runtime.
"""
from __future__ import annotations
import asyncio
import os
import uuid

import structlog

from scenarios.tcw.shared.mock_client import (
    query_customer_graph,
    score_propensity,
    check_eligibility,
    dispatch_channel,
)

log = structlog.get_logger(__name__)
_STEP_NAMES = ["graph_query", "propensity_score", "eligibility_check",
               "offer_personalize", "channel_dispatch"]


def _make_model():
    from harness.frameworks.autogen_llm import chat_client
    return chat_client()


def _make_agents():
    from autogen_agentchat.agents import AssistantAgent
    m = _make_model()
    return [
        AssistantAgent("GraphAgent", model_client=m,
                       system_message="Query customer graph. Acknowledge: step graph_query done."),
        AssistantAgent("PropensityAgent", model_client=m,
                       system_message="Run propensity model. Acknowledge: step propensity_score done."),
        AssistantAgent("EligibilityAgent", model_client=m,
                       system_message="Check eligibility rules. Acknowledge: step eligibility_check done."),
        AssistantAgent("PersonalizeAgent", model_client=m,
                       system_message="Generate personalised offer. Acknowledge: step offer_personalize done."),
        AssistantAgent("DispatchAgent", model_client=m,
                       system_message="Dispatch offer to channel. Say WORKFLOW_COMPLETE when done."),
    ]


async def _run_team(workflow_id: str, customer_id: str) -> dict:
    if os.environ.get("DRY_RUN") == "true":
        log.info("dry_run_mode", impl="fixed", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "step_log": list(_STEP_NAMES)}

    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    termination = TextMentionTermination("WORKFLOW_COMPLETE") | MaxMessageTermination(12)
    team = RoundRobinGroupChat(_make_agents(), termination_condition=termination)
    task = (f"Execute TCW for customer {customer_id}, workflow {workflow_id}. "
            f"Each agent runs its step and acknowledges completion in order.")
    await team.run(task=task)
    return {"workflow_id": workflow_id, "step_log": list(_STEP_NAMES)}


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    return asyncio.run(_run_team(workflow_id, customer_id))
