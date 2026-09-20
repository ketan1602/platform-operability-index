"""LangChain tool definitions wrapping GEW mock_client calls.

Tool creation is deferred so langchain_core is imported lazily —
the harness core stays importable without it installed.
"""
from __future__ import annotations
import json

_tools: list | None = None


def get_tools() -> list:
    """Return the list of LangChain Tool objects (created once, cached)."""
    global _tools
    if _tools is not None:
        return _tools
    from langchain_core.tools import tool

    @tool
    def get_system_a_data(dummy: str = "") -> str:
        """Fetch data from external system A."""
        from scenarios.gew.shared.mock_client import fetch_data
        return json.dumps(fetch_data("system_a"))

    @tool
    def get_system_b_data(dummy: str = "") -> str:
        """Fetch data from external system B."""
        from scenarios.gew.shared.mock_client import fetch_data
        return json.dumps(fetch_data("system_b"))

    @tool
    def risk_score_tool(evidence_id: str, evidence_data_json: str) -> str:
        """Score risk given evidence_id and JSON-encoded evidence_data."""
        from scenarios.gew.shared.mock_client import score_risk
        return json.dumps(score_risk(evidence_id, json.loads(evidence_data_json)))

    @tool
    def crm_update_tool(
        idempotency_key: str, customer_id: str, action: str, data_json: str
    ) -> str:
        """Write to CRM with idempotency protection."""
        from scenarios.gew.shared.mock_client import update_crm
        return json.dumps(
            update_crm(idempotency_key, customer_id, action, json.loads(data_json))
        )

    @tool
    def approval_request_tool(workflow_id: str, step: str, data_json: str) -> str:
        """Submit a HITL approval request; returns JSON with request_id."""
        from scenarios.gew.shared.mock_client import request_approval
        req_id = request_approval(workflow_id, step, json.loads(data_json))
        return json.dumps({"request_id": req_id})

    @tool
    def approval_status_tool(request_id: str) -> str:
        """Poll HITL approval status; returns JSON with status field."""
        from scenarios.gew.shared.mock_client import get_approval_status
        return json.dumps({"status": get_approval_status(request_id)})

    _tools = [
        get_system_a_data,
        get_system_b_data,
        risk_score_tool,
        crm_update_tool,
        approval_request_tool,
        approval_status_tool,
    ]
    return _tools
