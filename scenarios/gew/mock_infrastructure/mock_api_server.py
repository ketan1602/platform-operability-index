import hashlib
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

log = structlog.get_logger()

SYSTEM_A_DATA: dict[str, Any] = {
    "customer_id": "C-001",
    "name": "Acme Corp",
    "account_type": "enterprise",
    "region": "EMEA",
    "annual_value": 250000,
    "risk_flags": ["late_payment_q3", "contract_renewal_pending"],
    "evidence_id": "EVD-A-001",
}

SYSTEM_B_DATA: dict[str, Any] = {
    "customer_id": "C-001",
    "transaction_count_90d": 47,
    "avg_transaction_value": 12500,
    "dispute_count_90d": 2,
    "churn_signal": "moderate",
    "evidence_id": "EVD-B-001",
}

SEED_DATA: dict[str, dict] = {
    "system_a": SYSTEM_A_DATA,
    "system_b": SYSTEM_B_DATA,
}

RISK_THRESHOLDS: list[tuple[float, str]] = [
    (0.3, "low"),
    (0.6, "medium"),
    (0.85, "high"),
]

app = FastAPI(title="GEW Mock API Server", version="1.0.0")


class RiskRequest(BaseModel):
    evidence_id: str
    evidence_data: dict[str, Any]


def _score_from_evidence_id(evidence_id: str) -> float:
    digest = hashlib.sha256(evidence_id.encode()).hexdigest()
    raw = int(digest[:8], 16)
    return raw / 0xFFFFFFFF


def _risk_level(score: float) -> str:
    for threshold, level in RISK_THRESHOLDS:
        if score < threshold:
            return level
    return "critical"


def _rationale(score: float, level: str) -> str:
    return (
        f"Deterministic risk assessment yielded score {score:.4f}; "
        f"classified as {level} based on evidence_id hash."
    )


@app.get("/health")
def health() -> dict:
    log.info("health_check", service="mock-api-server")
    return {"status": "ok", "service": "mock-api-server", "port": 8001}


@app.get("/external/data")
def external_data(source: str = Query(...)) -> dict:
    payload = SEED_DATA.get(source)
    if payload is None:
        log.warning("unknown_source", source=source)
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")
    log.info("external_data_retrieved", source=source)
    return payload


@app.post("/risk/score")
def risk_score(req: RiskRequest) -> dict:
    score = _score_from_evidence_id(req.evidence_id)
    level = _risk_level(score)
    log.info("risk_scored", evidence_id=req.evidence_id, score=score, level=level)
    return {
        "risk_score": round(score, 6),
        "risk_level": level,
        "rationale": _rationale(score, level),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
