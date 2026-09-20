"""ML endpoint stub — FastAPI server for propensity scoring and eligibility checks.

Port: 8102 (set ML_ENDPOINT_URL=http://localhost:8102 in consumers).
"""
from __future__ import annotations
import random
from typing import Any
from fastapi import FastAPI
from pydantic import BaseModel
import structlog

log = structlog.get_logger(__name__)
app = FastAPI(title="TCW ML Endpoint", version="1.0.0")

_PRODUCTS = ["tv_bundle", "roaming_pack", "5g_upgrade", "device_protection", "cloud_storage"]
_ELIGIBILITY_RULES = {
    "tv_bundle": lambda f: f.get("contract_status") == "active",
    "roaming_pack": lambda f: "mobile_postpaid" in f.get("products", []),
    "5g_upgrade": lambda f: f.get("segment") in ("high_value", "medium_value"),
    "device_protection": lambda _: True,
    "cloud_storage": lambda _: True,
}


class ScoreRequest(BaseModel):
    customer_id: str
    features: dict[str, Any]


class EligibilityRequest(BaseModel):
    customer_id: str
    candidates: list[dict[str, Any]]


@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-endpoint"}


@app.post("/propensity/score")
def score_propensity(req: ScoreRequest):
    seed = sum(ord(c) for c in req.customer_id)
    rng = random.Random(seed)
    scores = [
        {"product_id": p, "score": round(rng.uniform(0.3, 0.95), 3)}
        for p in _PRODUCTS
    ]
    scores.sort(key=lambda x: x["score"], reverse=True)
    top3 = scores[:3]
    log.info("propensity_scored", customer_id=req.customer_id, top=top3[0]["product_id"])
    return {"customer_id": req.customer_id, "recommendations": top3}


@app.post("/eligibility/check")
def check_eligibility(req: EligibilityRequest):
    features = req.candidates[0] if req.candidates else {}
    eligible = [
        c for c in req.candidates
        if _ELIGIBILITY_RULES.get(c["product_id"], lambda _: True)(features)
    ]
    log.info("eligibility_checked", customer_id=req.customer_id, eligible=len(eligible))
    return {"customer_id": req.customer_id, "eligible": eligible}
