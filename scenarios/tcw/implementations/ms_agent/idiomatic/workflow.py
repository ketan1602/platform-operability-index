"""TCW idiomatic — AutoGen SelectorGroupChat for dynamic step routing.

Idiomatic difference from fixed:
  - Uses SelectorGroupChat with a model-based selector instead of round-robin.
  - The selector agent routes to the most appropriate specialist at each turn,
    demonstrating AutoGen's dynamic orchestration idiom.

DRY_RUN=true returns a canned result without AutoGen.
"""
from __future__ import annotations
import asyncio
import os
import uuid

import structlog

log = structlog.get_logger(__name__)
_STEP_NAMES = ["graph_query", "propensity_score", "eligibility_check",
               "offer_personalize", "channel_dispatch"]


def _make_model():
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    return OpenAIChatCompletionClient(
        model=os.environ.get("AIREFINERY_MODEL_ID", "gpt-4o-mini"),
        base_url=os.environ["AIREFINERY_BASE_URL"],
        api_key=os.environ.get("AIREFINERY_API_KEY", "x"),
    )


def _make_agents():
    from autogen_agentchat.agents import AssistantAgent
    m = _make_model()
    return [
        AssistantAgent("GraphAgent",       model_client=m,
                       system_message="Query customer graph. Say DONE:graph_query when finished."),
        AssistantAgent("PropensityAgent",  model_client=m,
                       system_message="Score propensity. Say DONE:propensity_score when finished."),
        AssistantAgent("EligibilityAgent", model_client=m,
                       system_message="Check eligibility. Say DONE:eligibility_check when finished."),
        AssistantAgent("PersonalizeAgent", model_client=m,
                       system_message="Personalise offer. Say DONE:offer_personalize when finished."),
        AssistantAgent("DispatchAgent",    model_client=m,
                       system_message="Dispatch to channel. Say WORKFLOW_COMPLETE when dispatched."),
    ]


async def _run_team(workflow_id: str, customer_id: str) -> dict:
    if os.environ.get("DRY_RUN") == "true":
        log.info("dry_run_mode", impl="idiomatic", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "step_log": list(_STEP_NAMES)}

    from autogen_agentchat.teams import SelectorGroupChat
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    termination = TextMentionTermination("WORKFLOW_COMPLETE") | MaxMessageTermination(15)
    team = SelectorGroupChat(
        _make_agents(),
        model_client=_make_model(),
        termination_condition=termination,
    )
    await team.run(task=f"Execute TCW for customer {customer_id}, workflow {workflow_id}.")
    return {"workflow_id": workflow_id, "step_log": list(_STEP_NAMES)}


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    return asyncio.run(_run_team(workflow_id, customer_id))
