"""Neo4j stub — FastAPI server simulating a customer graph database.

Responds to customer graph queries without a real Neo4j instance.
Port: 8101 (set NEO4J_STUB_URL=http://localhost:8101 in consumers).
"""
from __future__ import annotations
import random
from fastapi import FastAPI, HTTPException
import structlog

log = structlog.get_logger(__name__)
app = FastAPI(title="TCW Neo4j Stub", version="1.0.0")

_SEGMENTS = ["high_value", "medium_value", "churner", "new_customer"]
_PRODUCTS_MAP = {
    "high_value": ["mobile_postpaid", "broadband", "tv_bundle"],
    "medium_value": ["mobile_postpaid", "broadband"],
    "churner": ["mobile_prepaid"],
    "new_customer": ["mobile_postpaid"],
}


def _build_customer(customer_id: str) -> dict:
    seed = sum(ord(c) for c in customer_id)
    rng = random.Random(seed)
    segment = _SEGMENTS[seed % len(_SEGMENTS)]
    return {
        "customer_id": customer_id,
        "segment": segment,
        "tenure_months": rng.randint(1, 120),
        "products": _PRODUCTS_MAP[segment],
        "last_interaction": "2025-09-10",
        "opt_out": rng.random() < 0.05,
        "contract_status": "active" if segment != "churner" else "expired",
        "lifetime_value": round(rng.uniform(200, 5000), 2),
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "neo4j-stub"}


@app.get("/graph/customer/{customer_id}")
def get_customer_graph(customer_id: str):
    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id required")
    data = _build_customer(customer_id)
    log.info("graph_query", customer_id=customer_id, segment=data["segment"])
    return data


@app.get("/graph/customer/{customer_id}/neighbours")
def get_neighbours(customer_id: str, depth: int = 1):
    neighbours = [
        _build_customer(f"{customer_id}-nbr-{i}") for i in range(min(depth * 2, 5))
    ]
    return {"customer_id": customer_id, "neighbours": neighbours}
