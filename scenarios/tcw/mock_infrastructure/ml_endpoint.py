"""ML endpoint stub — FastAPI server for propensity scoring and eligibility checks.

Port: 8102 (HTTP). MCP port: 9102.
"""
from __future__ import annotations
import os
import random
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

log = structlog.get_logger(__name__)
app = FastAPI(title="TCW ML Endpoint", version="1.0.0")
mcp_app = FastMCP("tcw-ml-endpoint")

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


def _propensity_scores(customer_id: str) -> list[dict]:
    seed = sum(ord(c) for c in customer_id)
    rng = random.Random(seed)
    scores = [{"product_id": p, "score": round(rng.uniform(0.3, 0.95), 3)} for p in _PRODUCTS]
    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores[:3]


def _record_scored(customer_id: str, top_score: float) -> None:
    if os.environ.get("POI_LEDGER"):
        from harness.shared import ledger
        ledger.record("tcw_ml_scored", customer_id=customer_id, score=top_score)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-endpoint"}


@app.post("/propensity/score")
def score_propensity(req: ScoreRequest):
    if os.environ.get("POI_TCW_FAULT") == "1":
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="ml endpoint: model unavailable")
    top3 = _propensity_scores(req.customer_id)
    log.info("propensity_scored", customer_id=req.customer_id, top=top3[0]["product_id"])
    _record_scored(req.customer_id, top3[0]["score"])
    return {"customer_id": req.customer_id, "recommendations": top3}


@app.post("/eligibility/check")
def check_eligibility(req: EligibilityRequest):
    features = req.candidates[0] if req.candidates else {}
    eligible = [c for c in req.candidates
                if _ELIGIBILITY_RULES.get(c["product_id"], lambda _: True)(features)]
    log.info("eligibility_checked", customer_id=req.customer_id, eligible=len(eligible))
    return {"customer_id": req.customer_id, "eligible": eligible}


@mcp_app.tool()
def score_churn(customer_id: str, features: dict) -> dict:
    """Score churn propensity for a customer. Returns top product recommendations."""
    if os.environ.get("POI_TCW_FAULT") == "1":
        raise RuntimeError("ml endpoint: model unavailable")
    top3 = _propensity_scores(customer_id)
    churn_risk = "high" if features.get("contract_status") != "active" else "low"
    log.info("mcp_churn_scored", customer_id=customer_id, churn_risk=churn_risk)
    _record_scored(customer_id, top3[0]["score"])
    return {"customer_id": customer_id, "churn_risk": churn_risk, "recommendations": top3}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8102)
