"""GEW idiomatic — LangGraph StateGraph with conditional routing.

Idiomatic difference from fixed:
  - After step2, route_after_risk() forks on risk_level:
      low  → step4_action_execution (skip HITL gate)
      else → step3_hitl_gate → step4_action_execution
  - Both paths reconverge at step4 then step5.
  - Demonstrates the conditional-edge pattern that is LangGraph's core idiom.

DRY_RUN behaviour: same as fixed (mock server determines risk level).
"""
from __future__ import annotations
import structlog

from scenarios.gew.implementations.langgraph.fixed.workflow import (
    GEWState,
    step1_data_retrieval,
    step2_risk_assessment,
    step3_hitl_gate,
    step4_action_execution,
    step5_audit,
)

log = structlog.get_logger(__name__)


def route_after_risk(state: GEWState) -> str:
    level = (state.get("risk_assessment") or {}).get("risk_level", "high")
    dest = "step4_action_execution" if level == "low" else "step3_hitl_gate"
    log.info("route_after_risk", risk_level=level, next_node=dest)
    return dest


def build_graph(checkpointer=None, interrupt_after: list[str] | None = None):
    """Compile the idiomatic GEW graph with conditional risk routing."""
    from langgraph.graph import StateGraph, END
    from scenarios.gew.implementations.langgraph.fixed.checkpoint import (
        build_checkpointer as _build_cp,
    )

    cp = checkpointer if checkpointer is not None else _build_cp()
    builder = StateGraph(GEWState)
    builder.add_node("step1_data_retrieval", step1_data_retrieval)
    builder.add_node("step2_risk_assessment", step2_risk_assessment)
    builder.add_node("step3_hitl_gate", step3_hitl_gate)
    builder.add_node("step4_action_execution", step4_action_execution)
    builder.add_node("step5_audit", step5_audit)

    builder.set_entry_point("step1_data_retrieval")
    builder.add_edge("step1_data_retrieval", "step2_risk_assessment")
    builder.add_conditional_edges(
        "step2_risk_assessment",
        route_after_risk,
        {
            "step3_hitl_gate": "step3_hitl_gate",
            "step4_action_execution": "step4_action_execution",
        },
    )
    builder.add_edge("step3_hitl_gate", "step4_action_execution")
    builder.add_edge("step4_action_execution", "step5_audit")
    builder.add_edge("step5_audit", END)

    compile_kwargs: dict = {"checkpointer": cp}
    if interrupt_after:
        compile_kwargs["interrupt_after"] = interrupt_after
    return builder.compile(**compile_kwargs)


def run_workflow(
    workflow_id: str,
    checkpointer=None,
    config_overrides: dict | None = None,
) -> GEWState:
    graph = build_graph(checkpointer)
    config: dict = {"configurable": {"thread_id": workflow_id}}
    if config_overrides:
        config.update(config_overrides)
    return graph.invoke({"workflow_id": workflow_id, "step_log": []}, config)
