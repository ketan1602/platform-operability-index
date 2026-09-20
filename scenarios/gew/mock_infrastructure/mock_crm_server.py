import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

log = structlog.get_logger()

_receipts: dict[str, dict] = {}

app = FastAPI(title="GEW Mock CRM Server", version="1.0.0")


class CrmUpdateRequest(BaseModel):
    idempotency_key: str
    customer_id: str
    action: str
    data: dict[str, Any]


def _new_receipt(
    idempotency_key: str,
    customer_id: str,
    action: str,
    data: dict,
) -> dict:
    receipt_id = f"RCP-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    return {
        "receipt_id": receipt_id,
        "idempotency_key": idempotency_key,
        "customer_id": customer_id,
        "action": action,
        "data": data,
        "status": "processed",
        "already_processed": False,
        "timestamp": now,
    }


@app.get("/health")
def health() -> dict:
    log.info("health_check", service="mock-crm-server")
    return {"status": "ok", "service": "mock-crm-server", "port": 8002}


@app.post("/crm/update")
def crm_update(req: CrmUpdateRequest) -> dict:
    existing = _receipts.get(req.idempotency_key)
    if existing is not None:
        log.warning(
            "crm_duplicate_call",
            idempotency_key=req.idempotency_key,
            receipt_id=existing["receipt_id"],
        )
        return {**existing, "status": "already_processed", "already_processed": True}

    receipt = _new_receipt(
        req.idempotency_key, req.customer_id, req.action, req.data
    )
    _receipts[req.idempotency_key] = receipt
    log.info(
        "crm_updated",
        idempotency_key=req.idempotency_key,
        receipt_id=receipt["receipt_id"],
        action=req.action,
    )
    return receipt


@app.get("/crm/receipts/{idempotency_key}")
def get_receipt(idempotency_key: str) -> dict:
    receipt = _receipts.get(idempotency_key)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@app.delete("/crm/receipts")
def clear_receipts() -> dict:
    count = len(_receipts)
    _receipts.clear()
    log.info("receipts_cleared", count=count)
    return {"cleared": count}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
