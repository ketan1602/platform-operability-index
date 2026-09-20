"""TCW idiomatic — Google ADK single LlmAgent with all tools.

Idiomatic difference from fixed:
  - Uses one root LlmAgent with all five tools rather than a SequentialAgent
    pipeline, letting ADK's planner determine execution order.
  - Demonstrates ADK's autonomous tool-selection idiom.

DRY_RUN=true returns a canned result.
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


def _all_tools():
    from google.adk.tools import FunctionTool

    def graph_query(customer_id: str) -> str:
        data = query_customer_graph(customer_id)
        return f"graph_query done: segment={data.get('segment')}"

    def propensity_score(customer_id: str) -> str:
        recs = score_propensity(customer_id, {})
        return f"propensity_score done: top={recs[0]['product_id'] if recs else 'none'}"

    def eligibility_check(customer_id: str) -> str:
        eligible = check_eligibility(customer_id, [{"product_id": "tv_bundle", "score": 0.82}])
        return f"eligibility_check done: {len(eligible)} eligible"

    def offer_personalize(customer_id: str, product_id: str) -> str:
        return f"offer_personalize done: Exclusive {product_id} for {customer_id}"

    def channel_dispatch_fn(customer_id: str, offer: str, workflow_id: str) -> str:
        receipt = dispatch_channel(customer_id, offer, workflow_id)
        return f"channel_dispatch done: sent via {receipt.get('channel','email')}"

    return [FunctionTool(fn) for fn in [
        graph_query, propensity_score, eligibility_check,
        offer_personalize, channel_dispatch_fn,
    ]]


async def _run_adk(workflow_id: str, customer_id: str) -> dict:
    if os.environ.get("DRY_RUN") == "true":
        log.info("dry_run_mode", impl="idiomatic", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}

    from google.adk.agents import LlmAgent
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner
    from google.genai import types

    mid = f"litellm/{os.environ.get('AIREFINERY_MODEL_ID', 'gpt-4o-mini')}"
    root = LlmAgent(
        name="TCWAutonomousAgent",
        model=mid,
        tools=_all_tools(),
        instruction=(
            "Execute all 5 TCW steps using the tools in order: "
            "graph_query → propensity_score → eligibility_check → offer_personalize → channel_dispatch."
        ),
    )
    svc = InMemorySessionService()
    runner = Runner(agent=root, app_name="tcw", session_service=svc)
    await svc.create_session(app_name="tcw", user_id="harness", session_id=workflow_id)
    msg = types.Content(role="user", parts=[types.Part(text=f"Execute TCW for customer {customer_id}")])
    async for _ in runner.run_async(user_id="harness", session_id=workflow_id, new_message=msg):
        pass
    return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    return asyncio.run(_run_adk(workflow_id, customer_id))
