"""OpenAI Agents SDK tool definitions for the GEW fixed implementation.

Plain functions are defined first; _wrap_tools() applies @function_tool inside
a function body to satisfy the "no top-level framework imports" rule.
All tools return str — required by the OpenAI Agents SDK function_tool contract.
"""
from __future__ import annotations
import json


def get_system_a_data() -> str:
    """Fetch external data from system_a."""
    from scenarios.gew.shared.mock_client import fetch_data
    return json.dumps(fetch_data("system_a"))


def get_system_b_data() -> str:
    """Fetch external data from system_b."""
    from scenarios.gew.shared.mock_client import fetch_data
    return json.dumps(fetch_data("system_b"))


def score_risk_tool(evidence_id: str, evidence_data: str) -> str:
    """Score risk. evidence_data is a JSON string."""
    from scenarios.gew.shared.mock_client import score_risk
    return json.dumps(score_risk(evidence_id, json.loads(evidence_data)))


def crm_update_tool(idempotency_key: str, customer_id: str, action: str, data: str) -> str:
    """Write to CRM with idempotency key. data is a JSON string."""
    from scenarios.gew.shared.mock_client import update_crm
    return json.dumps(update_crm(idempotency_key, customer_id, action, json.loads(data)))


def request_approval_tool(workflow_id: str, step: str, data: str) -> str:
    """Submit HITL approval request. data is a JSON string. Returns request_id."""
    from scenarios.gew.shared.mock_client import request_approval
    return request_approval(workflow_id, step, json.loads(data))


def auto_approve_tool() -> str:
    """Approve all pending HITL requests (test mode). Returns JSON list of approved ids."""
    from scenarios.gew.shared.mock_client import auto_approve_all
    return json.dumps(auto_approve_all())


def check_approval_status_tool(request_id: str) -> str:
    """Poll approval status. Returns 'pending' | 'approved' | 'rejected'."""
    from scenarios.gew.shared.mock_client import get_approval_status
    return get_approval_status(request_id)


_TOOL_NAMES = [
    "get_system_a_data",
    "get_system_b_data",
    "score_risk_tool",
    "crm_update_tool",
    "request_approval_tool",
    "auto_approve_tool",
    "check_approval_status_tool",
]


def _wrap_tools() -> None:
    """Apply function_tool to each plain function; re-assigns module-level names."""
    from agents import function_tool
    import sys
    module = sys.modules[__name__]
    for name in _TOOL_NAMES:
        setattr(module, name, function_tool(getattr(module, name)))


_wrap_tools()
