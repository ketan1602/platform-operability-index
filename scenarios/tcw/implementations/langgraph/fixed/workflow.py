"""TCW fixed workflow — LangGraph StateGraph with 5 deterministic nodes.

Steps: graph_query → propensity_score → eligibility_check → offer_personalize → channel_dispatch
"""
from __future__ import annotations
import os
from typing import TypedDict

import structlog

from scenarios.tcw.shared.mock_client import (
    query_customer_graph,
    score_propensity,
    check_eligibility,
    dispatch_channel,
)

log = structlog.get_logger(__name__)
_STEPS = ["graph_query", "propensity_score", "eligibility_check",
          "offer_personalize", "channel_dispatch"]


class TCWState(TypedDict):
    workflow_id: str
    customer_id: str
    graph_data: dict
    recommendations: list
    eligible_offers: list
    personalized_offer: str
    dispatch_receipt: dict
    step_log: list[str]


def _llm_personalize(customer_id: str, offer: dict) -> str:
    if os.environ.get("DRY_RUN") == "true":
        return f"[dry-run] exclusive offer for {customer_id}: {offer.get('product_id', 'upgrade')}"
    if not os.environ.get("AIREFINERY_BASE_URL"):
        return f"Exclusive offer: {offer.get('product_id', 'upgrade')}"
    from harness.shared.llm import make_langchain_llm
    return make_langchain_llm().invoke(
        f"1 sentence personalised telco offer for {customer_id} recommending {offer}"
    ).content


def _append(state: TCWState, name: str) -> list[str]:
    sl = list(state.get("step_log") or [])
    sl.append(name)
    return sl


def step1_graph_query(state: TCWState) -> dict:
    data = query_customer_graph(state["customer_id"])
    log.info("tcw.step1.done", wf=state["workflow_id"])
    return {"graph_data": data, "step_log": _append(state, "graph_query")}


def step2_propensity_score(state: TCWState) -> dict:
    recs = score_propensity(state["customer_id"], state["graph_data"])
    log.info("tcw.step2.done", wf=state["workflow_id"], recs=len(recs))
    return {"recommendations": recs, "step_log": _append(state, "propensity_score")}


def step3_eligibility_check(state: TCWState) -> dict:
    eligible = check_eligibility(state["customer_id"], state.get("recommendations") or [])
    log.info("tcw.step3.done", wf=state["workflow_id"], eligible=len(eligible))
    return {"eligible_offers": eligible, "step_log": _append(state, "eligibility_check")}


def step4_offer_personalize(state: TCWState) -> dict:
    offer = (state.get("eligible_offers") or [{}])[0]
    msg = _llm_personalize(state["customer_id"], offer)
    log.info("tcw.step4.done", wf=state["workflow_id"])
    return {"personalized_offer": msg, "step_log": _append(state, "offer_personalize")}


def step5_channel_dispatch(state: TCWState) -> dict:
    receipt = dispatch_channel(
        customer_id=state["customer_id"],
        offer=state.get("personalized_offer", ""),
        workflow_id=state["workflow_id"],
    )
    sl = _append(state, "channel_dispatch")
    log.info("tcw.step5.done", wf=state["workflow_id"], steps=sl)
    return {"dispatch_receipt": receipt, "step_log": sl}


def build_graph(checkpointer=None, interrupt_after=None):
    from langgraph.graph import StateGraph, END
    from scenarios.gew.implementations.langgraph.fixed.checkpoint import (
        build_checkpointer as _build_cp,
    )
    cp = checkpointer if checkpointer is not None else _build_cp()
    b = StateGraph(TCWState)
    b.add_node("step1_graph_query", step1_graph_query)
    b.add_node("step2_propensity_score", step2_propensity_score)
    b.add_node("step3_eligibility_check", step3_eligibility_check)
    b.add_node("step4_offer_personalize", step4_offer_personalize)
    b.add_node("step5_channel_dispatch", step5_channel_dispatch)
    b.set_entry_point("step1_graph_query")
    b.add_edge("step1_graph_query", "step2_propensity_score")
    b.add_edge("step2_propensity_score", "step3_eligibility_check")
    b.add_edge("step3_eligibility_check", "step4_offer_personalize")
    b.add_edge("step4_offer_personalize", "step5_channel_dispatch")
    b.add_edge("step5_channel_dispatch", END)
    kwargs: dict = {"checkpointer": cp}
    if interrupt_after:
        kwargs["interrupt_after"] = interrupt_after
    return b.compile(**kwargs)


def run_workflow(workflow_id: str, customer_id: str = "cust-001",
                 checkpointer=None, config_overrides=None) -> TCWState:
    if os.environ.get("DRY_RUN") == "true":
        log.info("tcw_lg_dry_run", impl="fixed", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEPS)}
    graph = build_graph(checkpointer)
    config: dict = {"configurable": {"thread_id": workflow_id}}
    if config_overrides:
        config.update(config_overrides)
    return graph.invoke({"workflow_id": workflow_id, "customer_id": customer_id, "step_log": []}, config)
