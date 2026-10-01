from __future__ import annotations
import uuid
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

log = structlog.get_logger()

_requests: dict[str, dict] = {}

app = FastAPI(title="GEW Approval Server", version="1.0.0")
mcp_app = FastMCP("gew-approval")


class ApprovalRequest(BaseModel):
    workflow_id: str
    step: str
    data: dict[str, Any]
    timeout_seconds: int = 300


def _new_record(workflow_id: str, step: str, data: dict, timeout_seconds: int) -> dict:
    request_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
    return {
        "request_id": request_id,
        "workflow_id": workflow_id,
        "step": step,
        "data": data,
        "timeout_seconds": timeout_seconds,
        "status": "pending",
    }


def _get_or_404(request_id: str) -> dict:
    record = _requests.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return record


def _set_status(request_id: str, status: str) -> dict:
    record = _get_or_404(request_id)
    record["status"] = status
    log.info("approval_status_changed", request_id=request_id, status=status)
    return {"ok": True, "request_id": request_id}


@app.get("/health")
def health() -> dict:
    log.info("health_check", service="approval-server")
    return {"status": "ok", "service": "approval-server", "port": 8003}


@app.post("/approval/request")
def create_request(req: ApprovalRequest) -> dict:
    record = _new_record(req.workflow_id, req.step, req.data, req.timeout_seconds)
    _requests[record["request_id"]] = record
    log.info("approval_requested", request_id=record["request_id"],
             workflow_id=req.workflow_id, step=req.step)
    return {"request_id": record["request_id"], "status": "pending"}


@app.get("/approval/status/{request_id}")
def get_status(request_id: str) -> dict:
    record = _get_or_404(request_id)
    return {"request_id": record["request_id"], "status": record["status"],
            "workflow_id": record["workflow_id"]}


@app.post("/approval/approve/{request_id}")
def approve(request_id: str) -> dict:
    return _set_status(request_id, "approved")


@app.post("/approval/reject/{request_id}")
def reject(request_id: str) -> dict:
    return _set_status(request_id, "rejected")


@app.post("/approval/auto-approve")
def auto_approve() -> dict:
    approved = [rid for rid, rec in _requests.items() if rec["status"] == "pending"]
    for rid in approved:
        _requests[rid]["status"] = "approved"
    log.info("auto_approved", count=len(approved))
    return {"approved": approved}


@app.delete("/approval/requests")
def clear_requests() -> dict:
    count = len(_requests)
    _requests.clear()
    log.info("requests_cleared", count=count)
    return {"cleared": count}


@mcp_app.tool()
def request_approval(customer_id: str, action: str) -> dict:
    """Submit a human-in-the-loop approval request. Returns request_id."""
    record = _new_record(
        workflow_id=f"wf-{customer_id}",
        step=action,
        data={"customer_id": customer_id, "action": action},
        timeout_seconds=300,
    )
    _requests[record["request_id"]] = record
    log.info("mcp_approval_requested", request_id=record["request_id"],
             customer_id=customer_id, action=action)
    return {"request_id": record["request_id"], "status": "pending"}


@mcp_app.tool()
def get_approval_status(request_id: str) -> dict:
    """Poll HITL gate. Returns status: pending | approved | rejected."""
    record = _requests.get(request_id)
    if record is None:
        raise ValueError(f"Approval request not found: {request_id}")
    return {"request_id": request_id, "status": record["status"]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
