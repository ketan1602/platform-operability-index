"""AutoGen implementation of the 5-step GEW fixed workflow.

Sequential agent execution — not a chat loop — to match the fixed DAG.
AutoGen imports are deferred inside run_workflow() to keep harness imports clean.

Env vars:
  LLM_BASE_URL / AIREFINERY_BASE_URL  — OpenAI-compatible endpoint
  LLM_API_KEY / AIREFINERY_API_KEY   — secret (injected via .env or Vault)
  LLM_MODEL / AIREFINERY_MODEL       — model name
  DRY_RUN              — if "true", agents return hardcoded dicts (no LLM)
"""
from __future__ import annotations

import json
import os

import structlog

from scenarios.gew.implementations.ms_agent.fixed.tools import (
    auto_approve_fn,
    check_approval_fn,
    get_system_a_data,
    get_system_b_data,
    request_approval_fn,
    score_risk_fn,
    update_crm_fn,
)

log = structlog.get_logger()

_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

_DRY_RUN_EVIDENCE = {
    "evidence_id": "dry-run-001",
    "system_a": {"customer_id": "C-001", "balance": 5000},
    "system_b": {"flags": [], "last_review": "2025-01-01"},
}
_DRY_RUN_RISK = {"risk_score": 0.1, "risk_level": "low", "rationale": "dry-run"}
_DRY_RUN_CRM = {"receipt_id": "rcpt-dry-001", "status": "ok", "already_processed": False}
_DRY_RUN_AUDIT = {"audit_id": "audit-dry-001", "status": "complete"}


def _make_client():
    """Return OpenAIChatCompletionClient for the configured endpoint, or None for dry-run."""
    if _DRY_RUN:
        return None
    from autogen_ext.models.openai import OpenAIChatCompletionClient  # deferred
    base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("AIREFINERY_BASE_URL", "")
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("AIREFINERY_API_KEY", "")
    model = os.environ.get("MODEL_ID") or os.environ.get("AIREFINERY_MODEL", "gpt-4o-mini")
    if not base_url or not api_key:
        raise EnvironmentError(
            "LLM_BASE_URL and LLM_API_KEY must be set "
            "(or set DRY_RUN=true for local testing)"
        )
    return OpenAIChatCompletionClient(model=model, base_url=base_url, api_key=api_key)


def _step1_fetch_data() -> dict:
    if _DRY_RUN:
        log.info("step_complete", step="step1_fetch_data", mode="dry_run")
        return _DRY_RUN_EVIDENCE
    data_a = get_system_a_data()
    data_b = get_system_b_data()
    evidence = {
        "evidence_id": f"ev-{data_a.get('id', 'unknown')}",
        "system_a": data_a,
        "system_b": data_b,
    }
    log.info("step_complete", step="step1_fetch_data", evidence_id=evidence["evidence_id"])
    return evidence


def _step2_score_risk(evidence: dict) -> dict:
    if _DRY_RUN:
        log.info("step_complete", step="step2_score_risk", mode="dry_run")
        return _DRY_RUN_RISK
    result = score_risk_fn(evidence["evidence_id"], evidence)
    log.info("step_complete", step="step2_score_risk", risk_level=result.get("risk_level"))
    return result


def _step3_hitl_gate(workflow_id: str, evidence: dict, risk: dict) -> str:
    if _DRY_RUN:
        log.info("step_complete", step="step3_hitl_gate", mode="dry_run")
        return "approved"
    request_id = request_approval_fn(workflow_id, "risk_review", {"evidence": evidence, "risk": risk})
    auto_approve_fn()
    status = check_approval_fn(request_id)
    log.info("step_complete", step="step3_hitl_gate", request_id=request_id, status=status)
    return status


def _step4_crm_write(workflow_id: str, evidence: dict, risk: dict) -> dict:
    idem_key = f"{workflow_id}-crm-step4"
    if _DRY_RUN:
        log.info("step_complete", step="step4_crm_write", mode="dry_run")
        return _DRY_RUN_CRM
    customer_id = evidence.get("system_a", {}).get("customer_id", "unknown")
    receipt = update_crm_fn(idem_key, customer_id, "risk_flagged", risk)
    log.info("step_complete", step="step4_crm_write", receipt_id=receipt.get("receipt_id"))
    return receipt


def _step5_audit(workflow_id: str, evidence: dict, risk: dict, approval: str, crm: dict) -> dict:
    if _DRY_RUN:
        log.info("step_complete", step="step5_audit", mode="dry_run")
        return _DRY_RUN_AUDIT
    record = {
        "audit_id": f"audit-{workflow_id}",
        "workflow_id": workflow_id,
        "evidence_id": evidence.get("evidence_id"),
        "risk_level": risk.get("risk_level"),
        "approval_status": approval,
        "crm_receipt_id": crm.get("receipt_id"),
        "status": "complete",
    }
    log.info("step_complete", step="step5_audit", audit_id=record["audit_id"])
    return record


def run_workflow(workflow_id: str) -> dict:
    """Execute the 5-step GEW workflow sequentially.

    Returns a dict with all step outputs and a step_log for P1 measurement.
    """
    log.info("workflow_start", framework="autogen", workflow_id=workflow_id)
    step_log: list[str] = []

    evidence = _step1_fetch_data()
    step_log.append("step1_fetch_data")

    risk = _step2_score_risk(evidence)
    step_log.append("step2_score_risk")

    approval = _step3_hitl_gate(workflow_id, evidence, risk)
    step_log.append("step3_hitl_gate")

    crm_receipt = _step4_crm_write(workflow_id, evidence, risk)
    step_log.append("step4_crm_write")

    audit_record = _step5_audit(workflow_id, evidence, risk, approval, crm_receipt)
    step_log.append("step5_audit")

    log.info("workflow_complete", workflow_id=workflow_id, steps=step_log)
    return {
        "workflow_id": workflow_id,
        "evidence_record": evidence,
        "risk_assessment": risk,
        "approval_status": approval,
        "crm_receipt": crm_receipt,
        "audit_record": audit_record,
        "step_log": step_log,
    }
