"""Strands Agents implementation of the 5-step GEW fixed workflow.

Architecture: one Agent per step, each scoped to only the tools it needs.
Agents are called sequentially; state flows through a plain Python dict.

Environment variables:
  DRY_RUN            — set to 'true' to skip agent execution entirely.
  AIREFINERY_BASE_URL — OpenAI-compatible endpoint (optional).
  AIREFINERY_MODEL    — model identifier (default: gpt-4o).
  AIREFINERY_API_KEY  — API key for the above endpoint.
"""
from __future__ import annotations

import os
import uuid

import structlog

log = structlog.get_logger()

_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
_BASE_URL = os.environ.get("AIREFINERY_BASE_URL", "")
_MODEL_ID = os.environ.get("AIREFINERY_MODEL", "gpt-4o")
_API_KEY = os.environ.get("AIREFINERY_API_KEY", "")

_HARDCODED_RESULT = {
    "evidence_record": {"system_a": {"dry": True}, "system_b": {"dry": True}},
    "risk_assessment": {"risk_score": 0, "risk_level": "low", "rationale": "dry-run"},
    "approval_status": "approved",
    "crm_receipt": {"receipt_id": "dry-receipt", "status": "ok"},
    "audit_record": {"workflow_id": "dry", "completed": True},
    "step_log": ["step1", "step2", "step3", "step4", "step5"],
}


def _build_model():
    """Return an OpenAIModel if credentials are present, else None (dry-run fallback)."""
    if not (_BASE_URL and _API_KEY):
        return None
    try:
        from strands.models.openai import OpenAIModel
        return OpenAIModel(
            model_id=_MODEL_ID,
            client_args={"base_url": _BASE_URL, "api_key": _API_KEY},
        )
    except ImportError as exc:
        raise RuntimeError("strands-agents not installed") from exc


def _make_agent(model, tools: list):
    try:
        from strands import Agent
        return Agent(model=model, tools=tools)
    except ImportError as exc:
        raise RuntimeError("strands-agents not installed") from exc


def _run_step1(agents: dict, state: dict) -> None:
    t = agents["step1"]
    resp = t("Fetch data from system_a and system_b and return both payloads as JSON.")
    state["evidence_record"] = {
        "raw_response": str(resp),
        "evidence_id": state["workflow_id"],
    }
    log.info("gew_step_done", step="step1", workflow_id=state["workflow_id"])
    state["step_log"].append("step1")


def _run_step2(agents: dict, state: dict) -> None:
    t = agents["step2"]
    ev_id = state["workflow_id"]
    resp = t(
        f"Score the risk for evidence_id='{ev_id}' using the evidence data "
        f"{state['evidence_record']}. Return the full risk assessment JSON."
    )
    state["risk_assessment"] = {"raw_response": str(resp)}
    log.info("gew_step_done", step="step2", workflow_id=state["workflow_id"])
    state["step_log"].append("step2")


def _run_step3(agents: dict, state: dict) -> None:
    t = agents["step3"]
    resp = t(
        f"Request approval for workflow_id='{state['workflow_id']}' step='step3' "
        f"with data {state['risk_assessment']}. Then call auto_approve_tool to approve it. "
        f"Finally, poll check_approval_status until it returns 'approved'. "
        f"Return the final status string."
    )
    state["approval_status"] = str(resp)
    log.info("gew_step_done", step="step3", workflow_id=state["workflow_id"])
    state["step_log"].append("step3")


def _run_step4(agents: dict, state: dict) -> None:
    t = agents["step4"]
    idem_key = f"{state['workflow_id']}-crm-step4"
    resp = t(
        f"Write to CRM with idempotency_key='{idem_key}', customer_id='customer-001', "
        f"action='update_risk', data={state['risk_assessment']}. Return the receipt JSON."
    )
    state["crm_receipt"] = {"raw_response": str(resp)}
    log.info("gew_step_done", step="step4", workflow_id=state["workflow_id"])
    state["step_log"].append("step4")


def _run_step5(agents: dict, state: dict) -> None:
    state["audit_record"] = {
        "workflow_id": state["workflow_id"],
        "evidence_record": state["evidence_record"],
        "risk_assessment": state["risk_assessment"],
        "approval_status": state["approval_status"],
        "crm_receipt": state["crm_receipt"],
        "completed": True,
    }
    log.info("gew_step_done", step="step5", workflow_id=state["workflow_id"])
    state["step_log"].append("step5")


_STEP_RUNNERS = [_run_step1, _run_step2, _run_step3, _run_step4, _run_step5]


def run_workflow(workflow_id: str | None = None) -> dict:
    """Execute the 5-step GEW. Returns full state dict including step_log."""
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())

    if _DRY_RUN:
        log.info("gew_dry_run", workflow_id=workflow_id)
        result = dict(_HARDCODED_RESULT)
        result["workflow_id"] = workflow_id
        return result

    from scenarios.gew.implementations.strands_agents.fixed.tools import get_tools

    tools = get_tools()
    model = _build_model()

    agents = {
        "step1": _make_agent(model, [tools["get_system_a_data"], tools["get_system_b_data"]]),
        "step2": _make_agent(model, [tools["score_risk_tool"]]),
        "step3": _make_agent(model, [
            tools["request_approval_tool"],
            tools["auto_approve_tool"],
            tools["check_approval_status"],
        ]),
        "step4": _make_agent(model, [tools["crm_update_tool"]]),
        "step5": _make_agent(model, []),
    }

    state: dict = {"workflow_id": workflow_id, "step_log": []}
    for runner in _STEP_RUNNERS:
        runner(agents, state)

    return state
