"""Framework-agnostic HTTP client for GEW mock infrastructure.

All five framework implementations import from here so tool signatures are
identical across fixed implementations — satisfying the POI spec requirement
for a common tool surface.

Env vars (set by docker-compose or test runner):
  MOCK_API_URL   — base URL of mock_api_server (required; ./infra.sh up writes it)
  MOCK_CRM_URL   — base URL of mock_crm_server (required; ./infra.sh up writes it)
  APPROVAL_URL   — base URL of approval_server (required; ./infra.sh up writes it)
"""
from __future__ import annotations
import os
import requests



def _url(var: str) -> str:
    value = os.environ.get(var, "")
    if not value:
        raise RuntimeError(f"{var} must be set (run ./infra.sh up)")
    return value

_TIMEOUT = 10


def fetch_data(source: str) -> dict:
    """Step 1 — fetch external data. source = 'system_a' | 'system_b'."""
    r = requests.get(f"{_url('MOCK_API_URL')}/external/data", params={"source": source}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def score_risk(evidence_id: str, evidence_data: dict) -> dict:
    """Step 2 — deterministic risk scoring. Returns {risk_score, risk_level, rationale}."""
    r = requests.post(
        f"{_url('MOCK_API_URL')}/risk/score",
        json={"evidence_id": evidence_id, "evidence_data": evidence_data},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def update_crm(idempotency_key: str, customer_id: str, action: str, data: dict) -> dict:
    """Step 4 — CRM write. Returns {receipt_id, status, already_processed}."""
    r = requests.post(
        f"{_url('MOCK_CRM_URL')}/crm/update",
        json={"idempotency_key": idempotency_key, "customer_id": customer_id,
              "action": action, "data": data},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def request_approval(workflow_id: str, step: str, data: dict) -> str:
    """Step 3 — submit HITL approval request. Returns request_id."""
    r = requests.post(
        f"{_url('APPROVAL_URL')}/approval/request",
        json={"workflow_id": workflow_id, "step": step, "data": data},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["request_id"]


def get_approval_status(request_id: str) -> str:
    """Poll HITL gate. Returns 'pending' | 'approved' | 'rejected'."""
    r = requests.get(f"{_url('APPROVAL_URL')}/approval/status/{request_id}", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["status"]


def auto_approve_all() -> list[str]:
    """Test utility — approve every pending request. Harness calls this in automated runs."""
    r = requests.post(f"{_url('APPROVAL_URL')}/approval/auto-approve", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["approved"]


def reset_crm_receipts() -> None:
    """Test utility — clear CRM idempotency store between P1-T3 runs."""
    r = requests.delete(f"{_url('MOCK_CRM_URL')}/crm/receipts", timeout=_TIMEOUT)
    r.raise_for_status()
