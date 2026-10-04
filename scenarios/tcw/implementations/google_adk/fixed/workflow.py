"""TCW fixed workflow — Google ADK SequentialAgent with 5 sub-agents.

Each sub-agent owns one TCW step and is called in order by the root SequentialAgent.
DRY_RUN=true returns a canned result without instantiating ADK.
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


def _make_sub_agents():
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool
    from harness.frameworks.adk_llm import llm

    def graph_query(customer_id: str) -> str:
        data = query_customer_graph(customer_id)
        return f"segment={data.get('segment')}"

    def propensity_score(customer_id: str) -> str:
        recs = score_propensity(customer_id, {})
        return f"top={recs[0]['product_id'] if recs else 'none'}"

    def eligibility_check(customer_id: str) -> str:
        eligible = check_eligibility(customer_id, [{"product_id": "tv_bundle", "score": 0.82}])
        return f"eligible={len(eligible)}"

    def offer_personalize(customer_id: str, product_id: str) -> str:
        return f"Exclusive {product_id} deal for {customer_id}"

    def channel_dispatch_fn(customer_id: str, offer: str, workflow_id: str) -> str:
        receipt = dispatch_channel(customer_id, offer, workflow_id)
        return f"sent via {receipt.get('channel','email')}"

    mid = llm()
    return [
        LlmAgent(name="GraphAgent",       model=mid, tools=[FunctionTool(graph_query)],       instruction="Call graph_query."),
        LlmAgent(name="PropensityAgent",  model=mid, tools=[FunctionTool(propensity_score)],  instruction="Call propensity_score."),
        LlmAgent(name="EligibilityAgent", model=mid, tools=[FunctionTool(eligibility_check)], instruction="Call eligibility_check."),
        LlmAgent(name="PersonalizeAgent", model=mid, tools=[FunctionTool(offer_personalize)], instruction="Call offer_personalize."),
        LlmAgent(name="DispatchAgent",    model=mid, tools=[FunctionTool(channel_dispatch_fn)],instruction="Call channel_dispatch_fn."),
    ]


async def _run_adk(workflow_id: str, customer_id: str) -> dict:
    if os.environ.get("DRY_RUN") == "true":
        log.info("dry_run_mode", impl="fixed", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}

    from google.adk.agents import SequentialAgent
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner

    root = SequentialAgent(name="TCWSequential", sub_agents=_make_sub_agents())
    svc = InMemorySessionService()
    runner = Runner(agent=root, app_name="tcw", session_service=svc)
    session = await svc.create_session(app_name="tcw", user_id="harness", session_id=workflow_id)
    from google.genai import types
    msg = types.Content(role="user", parts=[types.Part(text=f"Execute TCW for {customer_id}")])
    async for _ in runner.run_async(user_id="harness", session_id=workflow_id, new_message=msg):
        pass
    return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEP_NAMES)}


def run_workflow(workflow_id: str = None, customer_id: str = "cust-001") -> dict:
    workflow_id = workflow_id or str(uuid.uuid4())
    return asyncio.run(_run_adk(workflow_id, customer_id))
