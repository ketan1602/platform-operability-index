"""GEW tool functions for Google ADK SequentialAgent.

Google ADK tools are plain Python callables with descriptive docstrings.
Each function delegates to the shared mock client — no framework coupling.
"""
from __future__ import annotations

import structlog

from scenarios.gew.shared.mock_client import (
    fetch_data,
    score_risk,
    update_crm,
    request_approval,
    get_approval_status,
    auto_approve_all,
)

log = structlog.get_logger()


def get_system_a_data() -> dict:
    """Fetch evidence data from System A. Returns raw data dict."""
    result = fetch_data("system_a")
    log.info("tool_called", tool="get_system_a_data", keys=list(result.keys()))
    return result


def get_system_b_data() -> dict:
    """Fetch supplementary data from System B. Returns raw data dict."""
    result = fetch_data("system_b")
    log.info("tool_called", tool="get_system_b_data", keys=list(result.keys()))
    return result


def score_risk_tool(evidence_id: str, evidence_data: dict) -> dict:
    """Score risk from combined evidence. Returns risk_score, risk_level, rationale."""
    result = score_risk(evidence_id, evidence_data)
    log.info("tool_called", tool="score_risk_tool", risk_level=result.get("risk_level"))
    return result


def crm_update_tool(idempotency_key: str, customer_id: str, action: str, data: dict) -> dict:
    """Write to CRM with idempotency guarantee. Returns receipt_id, status, already_processed."""
    result = update_crm(idempotency_key, customer_id, action, data)
    log.info("tool_called", tool="crm_update_tool", receipt_id=result.get("receipt_id"))
    return result


def request_approval_tool(workflow_id: str, step: str, data: dict) -> str:
    """Submit a HITL approval request. Returns request_id string."""
    request_id = request_approval(workflow_id, step, data)
    log.info("tool_called", tool="request_approval_tool", request_id=request_id)
    return request_id


def auto_approve_tool() -> list:
    """Approve all pending HITL requests. Returns list of approved request_ids."""
    approved = auto_approve_all()
    log.info("tool_called", tool="auto_approve_tool", count=len(approved))
    return approved


def check_approval_status(request_id: str) -> str:
    """Poll HITL gate for a request. Returns 'pending' | 'approved' | 'rejected'."""
    status = get_approval_status(request_id)
    log.info("tool_called", tool="check_approval_status", request_id=request_id, status=status)
    return status
