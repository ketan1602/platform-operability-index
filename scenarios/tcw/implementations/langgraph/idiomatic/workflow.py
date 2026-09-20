"""TCW idiomatic — LangGraph with conditional routing after eligibility_check.

Idiomatic difference from fixed:
  - After step3_eligibility_check, route_after_eligibility forks:
      empty eligible → step5_channel_dispatch (no offer; send retention message)
      non-empty     → step4_offer_personalize → step5_channel_dispatch
  - Demonstrates conditional-edge pattern with LangGraph's routing idiom.

DRY_RUN behaviour: same as fixed (mock client handles it).
"""
from __future__ import annotations
import os
import structlog

from scenarios.tcw.implementations.langgraph.fixed.workflow import (
    TCWState,
    step1_graph_query,
    step2_propensity_score,
    step3_eligibility_check,
    step4_offer_personalize,
    step5_channel_dispatch,
    _STEPS,
)

log = structlog.get_logger(__name__)


def route_after_eligibility(state: TCWState) -> str:
    eligible = state.get("eligible_offers") or []
    dest = "step4_offer_personalize" if eligible else "step5_channel_dispatch"
    log.info("route_after_eligibility", eligible=len(eligible), next=dest)
    return dest


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
    b.add_conditional_edges(
        "step3_eligibility_check",
        route_after_eligibility,
        {
            "step4_offer_personalize": "step4_offer_personalize",
            "step5_channel_dispatch": "step5_channel_dispatch",
        },
    )
    b.add_edge("step4_offer_personalize", "step5_channel_dispatch")
    b.add_edge("step5_channel_dispatch", END)
    kwargs: dict = {"checkpointer": cp}
    if interrupt_after:
        kwargs["interrupt_after"] = interrupt_after
    return b.compile(**kwargs)


def run_workflow(workflow_id: str, customer_id: str = "cust-001",
                 checkpointer=None, config_overrides=None) -> TCWState:
    if os.environ.get("DRY_RUN") == "true":
        log.info("tcw_lg_dry_run", impl="idiomatic", workflow_id=workflow_id)
        return {"workflow_id": workflow_id, "customer_id": customer_id, "step_log": list(_STEPS)}
    graph = build_graph(checkpointer)
    config: dict = {"configurable": {"thread_id": workflow_id}}
    if config_overrides:
        config.update(config_overrides)
    return graph.invoke({"workflow_id": workflow_id, "customer_id": customer_id, "step_log": []}, config)
