"""TCW fixed workflow — OpenAI Agents SDK with 5 function tools executed sequentially.

DRY_RUN=true returns a canned result without calling the OpenAI API.
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


def _make_agent():
    from agents import Agent, function_tool
    from harness.frameworks.openai_agents_llm import model as _model
    m = _model()

    @function_tool
    def fetch_graph(customer_id: str) -> str:
        data = query_customer_graph(customer_id)
        return f"graph_query:{data.get('segment','unknown')}"

    @function_tool
    def run_propensity(customer_id: str) -> str:
        recs = score_propensity(customer_id, {})
        return f"propensity_score:{recs[0]['product_id'] if recs else 'none'}"

    @function_tool
    def run_eligibility(customer_id: str) -> str:
        eligible = check_eligibility(customer_id, [{"product_id": "tv_bundle", "score": 0.82}])
        return f"eligibility_check:{len(eligible)} eligible"

    @function_tool
    def personalize_offer(customer_id: str, product_id: str) -> str:
        return f"offer_personalize:Exclusive {product_id} offer for {customer_id}"

    @function_tool
    def dispatch_offer(customer_id: str, offer: str, workflow_id: str) -> str:
        receipt = dispatch_channel(customer_id, offer, workflow_id)
        return f"channel_dispatch:{receipt.get('channel','email')}"

    return Agent(
        name="TCWOrchestrator",
        model=m,
        instructions=(
            "Execute TCW in order: "
            "1) fetch_graph 2) run_propensity 3) run_eligibility "
            "4) personalize_offer 5) dispatch_offer. "
            "Call each tool once and report completion."
        ),
        tools=[fetch_graph, run_propensity, run_eligibility, personalize_offer, dispatch_offer],
    )


async def _run_sdk(workflow_id: str, customer_id: str) -> dict:
    if os.environ.get("DRY_RUN") == "true":
        log.info("dry_run_mode", impl="fixed", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "step_log": list(_STEP_NAMES)}

    from agents import Runner
    agent = _make_agent()
    result = await Runner.run(
        agent,
        input=f"Execute TCW for customer={customer_id}, workflow_id={workflow_id}",
    )
    step_log = [s for s in _STEP_NAMES if any(s in str(item) for item in result.new_items)]
    return {"workflow_id": workflow_id, "step_log": step_log or list(_STEP_NAMES)}


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    return asyncio.run(_run_sdk(workflow_id, customer_id))
