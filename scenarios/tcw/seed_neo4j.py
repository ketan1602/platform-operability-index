"""Seed the TCW customer graph into Neo4j — idempotent (MERGE), safe to re-run.

Labels are POI-prefixed so benchmark data never collides with other graphs in the database.
    python -m scenarios.tcw.seed_neo4j
"""
from __future__ import annotations
import os
import random

import structlog

log = structlog.get_logger(__name__)

SEGMENTS = ["high_value", "medium_value", "churner", "new_customer"]
PRODUCTS = {
    "high_value": ["mobile_postpaid", "broadband", "tv_bundle"],
    "medium_value": ["mobile_postpaid", "broadband"],
    "churner": ["mobile_prepaid"],
    "new_customer": ["mobile_postpaid"],
}
CUSTOMER_COUNT = 50
_MERGE = """
MERGE (c:POICustomer {customer_id: $customer_id})
SET c.segment = $segment, c.tenure_months = $tenure_months, c.last_interaction = $last_interaction,
    c.opt_out = $opt_out, c.contract_status = $contract_status, c.lifetime_value = $lifetime_value
WITH c
UNWIND $products AS pid
MERGE (p:POIProduct {product_id: pid})
MERGE (c)-[:HAS_PRODUCT]->(p)
"""


def build_customer(customer_id: str) -> dict:
    """Deterministic customer record — the same generator the old HTTP stub used."""
    seed = sum(ord(ch) for ch in customer_id)
    rng = random.Random(seed)
    segment = SEGMENTS[seed % len(SEGMENTS)]
    return {
        "customer_id": customer_id, "segment": segment, "tenure_months": rng.randint(1, 120),
        "products": PRODUCTS[segment], "last_interaction": "2025-09-10",
        "opt_out": rng.random() < 0.05, "contract_status": "active" if segment != "churner" else "expired",
        "lifetime_value": round(rng.uniform(200, 5000), 2),
    }


def driver():
    from neo4j import GraphDatabase
    for var in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        if not os.environ.get(var):
            raise RuntimeError(f"{var} must be set (run ./infra.sh up)")
    return GraphDatabase.driver(os.environ["NEO4J_URI"],
                                auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))


def main() -> None:
    with driver() as d:
        for i in range(1, CUSTOMER_COUNT + 1):
            d.execute_query(_MERGE, build_customer(f"cust-{i:03d}"))
    log.info("tcw_neo4j_seeded", customers=CUSTOMER_COUNT)


if __name__ == "__main__":
    main()
