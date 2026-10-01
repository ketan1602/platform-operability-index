"""Framework-agnostic client for TCW backing services.

Customer graph: real Neo4j (NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD), seeded by
scenarios.tcw.seed_neo4j. ML scoring and channel dispatch: HTTP stubs at
ML_ENDPOINT_URL and CHANNEL_ADAPTER_URL. All addresses come from the environment
(./infra.sh up writes them); a missing one is a loud error, never a default.

All functions return fixture data immediately when DRY_RUN=true,
so the entire TCW scenario is exercisable without running any server.
"""
from __future__ import annotations
import os
import requests

_TIMEOUT = 10
_GRAPH_QUERY = """
MATCH (c:POICustomer {customer_id: $customer_id})
OPTIONAL MATCH (c)-[:HAS_PRODUCT]->(p:POIProduct)
RETURN c, collect(p.product_id) AS products
"""


def _url(var: str) -> str:
    value = os.environ.get(var, "")
    if not value:
        raise RuntimeError(f"{var} must be set (run ./infra.sh up)")
    return value


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
    """Step 1 — fetch the customer 360 view from Neo4j."""
    if _dry():
        result = {**_GRAPH_FIXTURE, "customer_id": customer_id}
    else:
        from scenarios.tcw.seed_neo4j import driver
        with driver() as d:
            records = d.execute_query(_GRAPH_QUERY, customer_id=customer_id).records
        if not records:
            raise LookupError(f"customer {customer_id} not in graph — run python -m scenarios.tcw.seed_neo4j")
        result = {**dict(records[0]["c"]), "products": records[0]["products"]}
    if os.environ.get("POI_LEDGER"):
        from harness.shared import ledger
        ledger.record("tcw_graph_queried", customer_id=customer_id)
    return result


def score_propensity(customer_id: str, graph_data: dict) -> list:
    """Step 2 — run ML propensity model; returns ranked product recommendations."""
    if _dry():
        recs = _RECS_FIXTURE
    elif os.environ.get("POI_TCW_FAULT") == "1":
        raise RuntimeError("ml endpoint: model unavailable")
    else:
        r = requests.post(
            f"{_url('ML_ENDPOINT_URL')}/propensity/score",
            json={"customer_id": customer_id, "features": graph_data},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        recs = r.json()["recommendations"]
    if os.environ.get("POI_LEDGER"):
        from harness.shared import ledger
        top_score = recs[0]["score"] if recs else None
        ledger.record("tcw_ml_scored", customer_id=customer_id, score=top_score)
    return recs


def check_eligibility(customer_id: str, recommendations: list) -> list:
    """Step 3 — apply business rules; returns eligible subset."""
    if _dry():
        return _ELIGIBLE_FIXTURE
    r = requests.post(
        f"{_url('ML_ENDPOINT_URL')}/eligibility/check",
        json={"customer_id": customer_id, "candidates": recommendations},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["eligible"]


def dispatch_channel(customer_id: str, offer: str, workflow_id: str) -> dict:
    """Step 5 — dispatch personalised offer to best channel; returns receipt."""
    if _dry():
        result = {**_DISPATCH_FIXTURE, "workflow_id": workflow_id}
    else:
        r = requests.post(
            f"{_url('CHANNEL_ADAPTER_URL')}/channel/dispatch",
            json={"customer_id": customer_id, "offer": offer, "workflow_id": workflow_id},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        result = r.json()
    if os.environ.get("POI_LEDGER"):
        from harness.shared import ledger
        ledger.record("tcw_channel_dispatched", customer_id=customer_id,
                      channel=result.get("channel"))
    return result
