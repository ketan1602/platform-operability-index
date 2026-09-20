"""Framework-agnostic HTTP client for TCW mock infrastructure.

Env vars (set by docker-compose or test runner):
  NEO4J_STUB_URL      — base URL of neo4j_stub     (default: http://localhost:8101)
  ML_ENDPOINT_URL     — base URL of ml_endpoint     (default: http://localhost:8102)
  CHANNEL_ADAPTER_URL — base URL of channel_adapter (default: http://localhost:8103)

All functions return fixture data immediately when DRY_RUN=true,
so the entire TCW scenario is exercisable without running any server.
"""
from __future__ import annotations
import os
import requests

NEO4J_STUB_URL = os.environ.get("NEO4J_STUB_URL", "http://localhost:8101")
ML_ENDPOINT_URL = os.environ.get("ML_ENDPOINT_URL", "http://localhost:8102")
CHANNEL_ADAPTER_URL = os.environ.get("CHANNEL_ADAPTER_URL", "http://localhost:8103")
_TIMEOUT = 10


def _dry() -> bool:
    return os.environ.get("DRY_RUN") == "true"


_GRAPH_FIXTURE = {
    "segment": "high_value",
    "tenure_months": 36,
    "products": ["mobile_postpaid", "broadband"],
    "last_interaction": "2025-09-10",
    "opt_out": False,
    "contract_status": "active",
}
_RECS_FIXTURE = [
    {"product_id": "tv_bundle", "score": 0.82},
    {"product_id": "roaming_pack", "score": 0.67},
    {"product_id": "5g_upgrade", "score": 0.55},
]
_ELIGIBLE_FIXTURE = [{"product_id": "tv_bundle", "score": 0.82}]
_DISPATCH_FIXTURE = {"receipt_id": "dry-dispatch-001", "channel": "email", "status": "sent"}


def query_customer_graph(customer_id: str) -> dict:
    """Step 1 — fetch customer 360 view from Neo4j stub."""
    if _dry():
        return {**_GRAPH_FIXTURE, "customer_id": customer_id}
    r = requests.get(
        f"{NEO4J_STUB_URL}/graph/customer/{customer_id}", timeout=_TIMEOUT
    )
    r.raise_for_status()
    return r.json()


def score_propensity(customer_id: str, graph_data: dict) -> list:
    """Step 2 — run ML propensity model; returns ranked product recommendations."""
    if _dry():
        return _RECS_FIXTURE
    r = requests.post(
        f"{ML_ENDPOINT_URL}/propensity/score",
        json={"customer_id": customer_id, "features": graph_data},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["recommendations"]


def check_eligibility(customer_id: str, recommendations: list) -> list:
    """Step 3 — apply business rules; returns eligible subset."""
    if _dry():
        return _ELIGIBLE_FIXTURE
    r = requests.post(
        f"{ML_ENDPOINT_URL}/eligibility/check",
        json={"customer_id": customer_id, "candidates": recommendations},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["eligible"]


def dispatch_channel(customer_id: str, offer: str, workflow_id: str) -> dict:
    """Step 5 — dispatch personalised offer to best channel; returns receipt."""
    if _dry():
        return {**_DISPATCH_FIXTURE, "workflow_id": workflow_id}
    r = requests.post(
        f"{CHANNEL_ADAPTER_URL}/channel/dispatch",
        json={"customer_id": customer_id, "offer": offer, "workflow_id": workflow_id},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
