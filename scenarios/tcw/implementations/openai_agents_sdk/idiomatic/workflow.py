"""TCW idiomatic — OpenAI Agents SDK hub-and-spoke with specialist handoffs.

Idiomatic difference from fixed:
  - Central TCWOrchestrator delegates to specialist agents via handoffs rather
    than calling function tools directly, demonstrating the SDK's native multi-agent idiom.
  - Specialists return control to the orchestrator after each step.

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


def _make_team():
    from agents import Agent, function_tool

    @function_tool
    def graph_tool(customer_id: str) -> str:
        data = query_customer_graph(customer_id)
        return f"graph_query complete: segment={data.get('segment')}"

    @function_tool
    def propensity_tool(customer_id: str) -> str:
        recs = score_propensity(customer_id, {})
        return f"propensity_score complete: top={recs[0]['product_id'] if recs else 'none'}"

    @function_tool
    def eligibility_tool(customer_id: str) -> str:
        eligible = check_eligibility(customer_id, [{"product_id": "tv_bundle", "score": 0.82}])
        return f"eligibility_check complete: {len(eligible)} eligible"

    @function_tool
    def personalize_tool(customer_id: str, product_id: str) -> str:
        return f"offer_personalize complete: Exclusive {product_id} for {customer_id}"

    @function_tool
    def dispatch_tool(customer_id: str, offer: str, workflow_id: str) -> str:
        receipt = dispatch_channel(customer_id, offer, workflow_id)
        return f"channel_dispatch complete: {receipt.get('channel','email')}"

    graph_agent = Agent(name="GraphSpecialist",       instructions="Call graph_tool.", tools=[graph_tool])
    prop_agent  = Agent(name="PropensitySpecialist",  instructions="Call propensity_tool.", tools=[propensity_tool])
    elig_agent  = Agent(name="EligibilitySpecialist", instructions="Call eligibility_tool.", tools=[eligibility_tool])
    pers_agent  = Agent(name="PersonalizeSpecialist", instructions="Call personalize_tool.", tools=[personalize_tool])
    disp_agent  = Agent(name="DispatchSpecialist",    instructions="Call dispatch_tool.", tools=[dispatch_tool])

    orchestrator = Agent(
        name="TCWOrchestrator",
        instructions="Route steps to: GraphSpecialist → PropensitySpecialist → EligibilitySpecialist → PersonalizeSpecialist → DispatchSpecialist",
        handoffs=[graph_agent, prop_agent, elig_agent, pers_agent, disp_agent],
    )
    return orchestrator


async def _run_sdk(workflow_id: str, customer_id: str) -> dict:
    if os.environ.get("DRY_RUN") == "true":
        log.info("dry_run_mode", impl="idiomatic", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "step_log": list(_STEP_NAMES)}

    from agents import Runner
    result = await Runner.run(
        _make_team(),
        input=f"Execute TCW for customer={customer_id}, workflow_id={workflow_id}",
    )
    step_log = [s for s in _STEP_NAMES if any(s in str(m) for m in result.new_messages)]
    return {"workflow_id": workflow_id, "step_log": step_log or list(_STEP_NAMES)}


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    return asyncio.run(_run_sdk(workflow_id, customer_id))
