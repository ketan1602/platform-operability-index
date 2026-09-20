"""Channel adapter stub — FastAPI server for multi-channel offer dispatch.

Supports email, SMS, and push-notification channels.
Port: 8103 (set CHANNEL_ADAPTER_URL=http://localhost:8103 in consumers).
"""
from __future__ import annotations
import uuid
from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel
import structlog

log = structlog.get_logger(__name__)
app = FastAPI(title="TCW Channel Adapter", version="1.0.0")

_receipts: dict[str, dict] = {}

Channel = Literal["email", "sms", "push"]

_CHANNEL_MAP: dict[str, Channel] = {
    "high_value": "email",
    "medium_value": "sms",
    "churner": "push",
    "new_customer": "email",
}


class DispatchRequest(BaseModel):
    customer_id: str
    offer: str
    workflow_id: str
    preferred_channel: Channel | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "channel-adapter"}


@app.post("/channel/dispatch")
def dispatch(req: DispatchRequest):
    channel: Channel = req.preferred_channel or "email"
    receipt_id = f"rcpt-{uuid.uuid4().hex[:8]}"
    receipt = {
        "receipt_id": receipt_id,
        "workflow_id": req.workflow_id,
        "customer_id": req.customer_id,
        "channel": channel,
        "status": "sent",
        "offer_preview": req.offer[:80],
    }
    _receipts[receipt_id] = receipt
    log.info(
        "offer_dispatched",
        customer_id=req.customer_id,
        channel=channel,
        receipt_id=receipt_id,
    )
    return receipt


@app.get("/channel/receipts/{receipt_id}")
def get_receipt(receipt_id: str):
    if receipt_id not in _receipts:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="receipt not found")
    return _receipts[receipt_id]


@app.delete("/channel/receipts")
def reset_receipts():
    _receipts.clear()
    return {"cleared": True}
