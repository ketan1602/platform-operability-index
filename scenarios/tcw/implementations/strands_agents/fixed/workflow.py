"""TCW fixed workflow — Strands Agents with 5 scoped single-tool agents.

Each agent is responsible for exactly one TCW step, executed by the caller in order.
DRY_RUN=true returns a canned result without starting a Strands runtime.
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


def _model():
    from strands.models.openai import OpenAIModel
    return OpenAIModel(
        model_id=os.environ.get("AIREFINERY_MODEL_ID", "gpt-4o-mini"),
        client_args={
            "base_url": os.environ["AIREFINERY_BASE_URL"],
            "api_key": os.environ.get("AIREFINERY_API_KEY", "x"),
        },
    )


def _run_step(step_name: str, prompt: str) -> str:
    from strands import Agent, tool

    @tool
    def noop_tool(data: str) -> str:
        """Return data unchanged."""
        return data

    agent = Agent(
        model=_model(),
        tools=[noop_tool],
        system_prompt=f"You are the {step_name} agent. {prompt}",
    )
    result = agent(prompt)
    return str(result)


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    if os.environ.get("DRY_RUN") == "true":
        log.info("gew_dry_run", impl="fixed", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}

    graph_data = query_customer_graph(customer_id)
    log.info("tcw.step1.done", wf=workflow_id)

    recs = score_propensity(customer_id, graph_data)
    log.info("tcw.step2.done", wf=workflow_id, recs=len(recs))

    eligible = check_eligibility(customer_id, recs)
    log.info("tcw.step3.done", wf=workflow_id, eligible=len(eligible))

    offer = (eligible or [{}])[0]
    _run_step("offer_personalize",
              f"Write 1-sentence offer for {customer_id} recommending {offer.get('product_id','upgrade')}")
    log.info("tcw.step4.done", wf=workflow_id)

    receipt = dispatch_channel(customer_id=customer_id, offer=str(offer), workflow_id=workflow_id)
    log.info("tcw.step5.done", wf=workflow_id, channel=receipt.get("channel"))

    return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}
