"""Plain Python tool functions for GEW AutoGen fixed implementation.

All tools delegate to scenarios.gew.shared.mock_client — same wire protocol
used by every framework implementation.
"""
from __future__ import annotations

from scenarios.gew.shared import mock_client


def get_system_a_data() -> dict:
    """Fetch evidence from System A."""
    return mock_client.fetch_data("system_a")


def get_system_b_data() -> dict:
    """Fetch evidence from System B."""
    return mock_client.fetch_data("system_b")


def score_risk_fn(evidence_id: str, evidence_data: dict) -> dict:
    """Score risk from combined evidence."""
    return mock_client.score_risk(evidence_id, evidence_data)


def update_crm_fn(
    idempotency_key: str,
    customer_id: str,
    action: str,
    data: dict,
) -> dict:
    """Write to CRM with idempotency key."""
    return mock_client.update_crm(idempotency_key, customer_id, action, data)


def request_approval_fn(workflow_id: str, step: str, data: dict) -> str:
    """Submit HITL approval request. Returns request_id."""
    return mock_client.request_approval(workflow_id, step, data)


def auto_approve_fn() -> list:
    """Auto-approve all pending requests (test mode)."""
    return mock_client.auto_approve_all()


def check_approval_fn(request_id: str) -> str:
    """Poll approval status. Returns 'pending' | 'approved' | 'rejected'."""
    return mock_client.get_approval_status(request_id)
