"""TCW idiomatic — Strands Agents single orchestrator with all tools.

Idiomatic difference from fixed:
  - Uses one orchestrator Agent holding all 5 tools rather than 5 scoped agents.
  - The orchestrator reasons about which tool to call next, demonstrating
    Strands' agentic loop idiom for multi-step workflows.

DRY_RUN=true returns a canned result.
"""
from __future__ import annotations
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


def _make_tools():
    from strands import tool

    @tool
    def graph_query(customer_id: str) -> str:
        """Fetch customer 360 view from the graph database."""
        data = query_customer_graph(customer_id)
        return f"graph_query: segment={data.get('segment')}, products={data.get('products')}"

    @tool
    def propensity_score(customer_id: str) -> str:
        """Run ML propensity model and return top recommendations."""
        recs = score_propensity(customer_id, {})
        return f"propensity_score: top={[r['product_id'] for r in recs[:3]]}"

    @tool
    def eligibility_check(customer_id: str) -> str:
        """Apply business eligibility rules to filter recommendations."""
        eligible = check_eligibility(customer_id, [{"product_id": "tv_bundle", "score": 0.82}])
        return f"eligibility_check: {len(eligible)} eligible offer(s)"

    @tool
    def offer_personalize(customer_id: str, product_id: str) -> str:
        """Generate a personalised offer message."""
        return f"offer_personalize: Exclusive {product_id} upgrade for {customer_id}"

    @tool
    def channel_dispatch_fn(customer_id: str, offer: str, workflow_id: str) -> str:
        """Dispatch offer to the best channel and return receipt."""
        receipt = dispatch_channel(customer_id, offer, workflow_id)
        return f"channel_dispatch: sent via {receipt.get('channel','email')}"

    return [graph_query, propensity_score, eligibility_check, offer_personalize, channel_dispatch_fn]


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    if os.environ.get("DRY_RUN") == "true":
        log.info("gew_dry_run", impl="idiomatic", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}

    from strands import Agent
    from strands.models.openai import OpenAIModel
    model = OpenAIModel(
        model_id=os.environ.get("AIREFINERY_MODEL", "openai/gpt-oss-120b"),
        client_args={
            "base_url": os.environ["AIREFINERY_BASE_URL"],
            "api_key": os.environ.get("AIREFINERY_API_KEY", "x"),
        },
    )
    orchestrator = Agent(
        model=model,
        tools=_make_tools(),
        system_prompt=(
            "Execute TCW using all tools in order: "
            "graph_query → propensity_score → eligibility_check → offer_personalize → channel_dispatch."
        ),
    )
    orchestrator(
        f"Execute the full TCW workflow for customer_id={customer_id}, workflow_id={workflow_id}"
    )
    log.info("tcw_strands_complete", workflow_id=workflow_id)
    return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}
