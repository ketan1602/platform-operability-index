"""Strands Agents tool definitions for the GEW fixed workflow.

Each @tool-decorated function delegates to the shared mock_client so that
tool signatures are identical across all framework implementations.
"""
from __future__ import annotations


def _tool():
    """Lazy import of the @tool decorator to allow ImportError fallback."""
    try:
        from strands import tool as _t
        return _t
    except ImportError as exc:
        raise RuntimeError(
            "strands-agents is not installed. Run: pip install strands-agents"
        ) from exc


def _register_tools():
    """Return a dict of tool-decorated callables, built lazily."""
    tool = _tool()
    from scenarios.gew.shared import mock_client

    @tool
    def get_system_a_data() -> dict:
        """Fetch raw data from System A (external data source)."""
        return mock_client.fetch_data("system_a")

    @tool
    def get_system_b_data() -> dict:
        """Fetch raw data from System B (external data source)."""
        return mock_client.fetch_data("system_b")

    @tool
    def score_risk_tool(evidence_id: str, evidence_data: dict) -> dict:
        """Score risk given an evidence record. Returns risk_score, risk_level, rationale."""
        return mock_client.score_risk(evidence_id, evidence_data)

    @tool
    def crm_update_tool(
        idempotency_key: str, customer_id: str, action: str, data: dict
    ) -> dict:
        """Write to CRM with an idempotency key. Returns receipt_id, status."""
        return mock_client.update_crm(idempotency_key, customer_id, action, data)

    @tool
    def request_approval_tool(workflow_id: str, step: str, data: dict) -> str:
        """Submit a HITL approval request. Returns the request_id string."""
        return mock_client.request_approval(workflow_id, step, data)

    @tool
    def auto_approve_tool() -> list:
        """Approve all pending HITL requests (test/automation utility)."""
        return mock_client.auto_approve_all()

    @tool
    def check_approval_status(request_id: str) -> str:
        """Poll HITL gate status. Returns 'pending' | 'approved' | 'rejected'."""
        return mock_client.get_approval_status(request_id)

    return {
        "get_system_a_data": get_system_a_data,
        "get_system_b_data": get_system_b_data,
        "score_risk_tool": score_risk_tool,
        "crm_update_tool": crm_update_tool,
        "request_approval_tool": request_approval_tool,
        "auto_approve_tool": auto_approve_tool,
        "check_approval_status": check_approval_status,
    }


# Module-level cache so tools are registered once per process.
_TOOLS: dict | None = None


def get_tools() -> dict:
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = _register_tools()
    return _TOOLS
