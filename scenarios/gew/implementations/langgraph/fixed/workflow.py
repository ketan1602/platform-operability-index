"""GEW fixed workflow — LangGraph StateGraph with 5 deterministic nodes."""
from __future__ import annotations
import json
import os
import time
from typing import TypedDict

import structlog

log = structlog.get_logger(__name__)


class GEWState(TypedDict):
    workflow_id: str
    system_a_data: dict
    system_b_data: dict
    evidence_record: dict
    risk_assessment: dict
    approval_id: str
    approval_status: str
    crm_receipt: dict
    audit_record: dict
    step_log: list[str]


def _summarise(prompt: str) -> str:
    if os.environ.get("DRY_RUN") == "true":
        return f"[dry-run] {prompt[:60]}"
    if not os.environ.get("AIREFINERY_BASE_URL"):
        return f"summary: {prompt[:80]}"
    from harness.shared.llm import make_langchain_llm
    return make_langchain_llm().invoke(prompt).content


def _append_step(state: GEWState, name: str) -> list[str]:
    log_list = list(state.get("step_log") or [])
    log_list.append(name)
    return log_list


def step1_data_retrieval(state: GEWState) -> dict:
    from scenarios.gew.shared.mock_client import fetch_data
    a = fetch_data("system_a")
    b = fetch_data("system_b")
    summary = _summarise(f"Combine systems: {json.dumps({'a': a, 'b': b})[:200]}")
    evidence = {"system_a": a, "system_b": b, "summary": summary}
    log.info("step1.done", workflow_id=state["workflow_id"])
    return {
        "system_a_data": a,
        "system_b_data": b,
        "evidence_record": evidence,
        "step_log": _append_step(state, "step1"),
    }


def step2_risk_assessment(state: GEWState) -> dict:
    from scenarios.gew.shared.mock_client import score_risk
    wid = state["workflow_id"]
    risk = score_risk(wid, state["evidence_record"])
    risk["llm_rationale"] = _summarise(f"Risk rationale: {json.dumps(risk)[:200]}")
    log.info("step2.done", workflow_id=wid, risk_level=risk.get("risk_level"))
    return {"risk_assessment": risk, "step_log": _append_step(state, "step2")}


def step3_hitl_gate(state: GEWState) -> dict:
    from scenarios.gew.shared.mock_client import request_approval, auto_approve_all, get_approval_status
    wid = state["workflow_id"]
    req_id = request_approval(wid, "step3", state["risk_assessment"])
    auto_approve_all()
    status = "pending"
    for _ in range(20):
        status = get_approval_status(req_id)
        if status != "pending":
            break
        time.sleep(0.05)
    log.info("step3.done", workflow_id=wid, approval_status=status)
    return {
        "approval_id": req_id,
        "approval_status": status,
        "step_log": _append_step(state, "step3"),
    }


def step4_action_execution(state: GEWState) -> dict:
    from scenarios.gew.shared.mock_client import update_crm
    wid = state["workflow_id"]
    receipt = update_crm(
        idempotency_key=f"{wid}-crm-step4",
        customer_id=wid,
        action="update",
        data=state["risk_assessment"],
    )
    log.info("step4.done", workflow_id=wid, receipt_id=receipt.get("receipt_id"))
    return {"crm_receipt": receipt, "step_log": _append_step(state, "step4")}


def step5_audit(state: GEWState) -> dict:
    wid = state["workflow_id"]
    audit = {
        "workflow_id": wid,
        "evidence_record": state["evidence_record"],
        "risk_assessment": state["risk_assessment"],
        "approval_id": state.get("approval_id"),
        "approval_status": state.get("approval_status"),
        "crm_receipt": state["crm_receipt"],
    }
    log_list = _append_step(state, "step5")
    log.info("step5.audit_written", workflow_id=wid, steps_completed=log_list)
    return {"audit_record": audit, "step_log": log_list}


def build_graph(checkpointer=None, interrupt_after: list[str] | None = None):
    """Compile the GEW StateGraph.

    Args:
        checkpointer: override the default checkpointer (from build_checkpointer()).
        interrupt_after: node names after which execution should pause (for T2 testing).
    """
    from langgraph.graph import StateGraph, END
    from .checkpoint import build_checkpointer as _build_cp
    cp = checkpointer if checkpointer is not None else _build_cp()
    builder = StateGraph(GEWState)
    builder.add_node("step1_data_retrieval", step1_data_retrieval)
    builder.add_node("step2_risk_assessment", step2_risk_assessment)
    builder.add_node("step3_hitl_gate", step3_hitl_gate)
    builder.add_node("step4_action_execution", step4_action_execution)
    builder.add_node("step5_audit", step5_audit)
    builder.set_entry_point("step1_data_retrieval")
    builder.add_edge("step1_data_retrieval", "step2_risk_assessment")
    builder.add_edge("step2_risk_assessment", "step3_hitl_gate")
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
