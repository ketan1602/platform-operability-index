"""Channel adapter stub — FastAPI server for multi-channel offer dispatch.

Supports email, SMS, and push-notification channels.
Port: 8103 (HTTP). MCP port: 9103.
"""
from __future__ import annotations
import os
import uuid
from typing import Literal

import structlog
import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

log = structlog.get_logger(__name__)
app = FastAPI(title="TCW Channel Adapter", version="1.0.0")
mcp_app = FastMCP("tcw-channel-adapter")

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


def _dispatch(customer_id: str, channel: Channel, offer: str, workflow_id: str) -> dict:
    receipt_id = f"rcpt-{uuid.uuid4().hex[:8]}"
    receipt = {
        "receipt_id": receipt_id,
        "workflow_id": workflow_id,
        "customer_id": customer_id,
        "channel": channel,
        "status": "sent",
        "offer_preview": offer[:80],
    }
    _receipts[receipt_id] = receipt
    log.info("offer_dispatched", customer_id=customer_id, channel=channel, receipt_id=receipt_id)
    if os.environ.get("POI_LEDGER"):
        from harness.shared import ledger
        ledger.record("tcw_channel_dispatched", customer_id=customer_id, channel=channel)
    return receipt


@app.get("/health")
def health():
    return {"status": "ok", "service": "channel-adapter"}


@app.post("/channel/dispatch")
def http_dispatch(req: DispatchRequest):
    channel: Channel = req.preferred_channel or "email"
    return _dispatch(req.customer_id, channel, req.offer, req.workflow_id)


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


@mcp_app.tool()
def dispatch_offer(customer_id: str, channel: str, offer: str) -> dict:
    """Dispatch a personalised offer to a customer via email, sms, or push."""
    safe_channel: Channel = channel if channel in ("email", "sms", "push") else "email"
    return _dispatch(customer_id, safe_channel, offer, workflow_id=f"wf-{customer_id}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8103)
