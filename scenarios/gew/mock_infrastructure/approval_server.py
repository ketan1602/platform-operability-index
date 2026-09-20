import uuid
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

log = structlog.get_logger()

_requests: dict[str, dict] = {}

app = FastAPI(title="GEW Approval Server", version="1.0.0")


class ApprovalRequest(BaseModel):
    workflow_id: str
    step: str
    data: dict[str, Any]
    timeout_seconds: int = 300


def _new_record(
    workflow_id: str,
    step: str,
    data: dict,
    timeout_seconds: int,
) -> dict:
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
    log.info(
        "approval_requested",
        request_id=record["request_id"],
        workflow_id=req.workflow_id,
        step=req.step,
    )
    return {"request_id": record["request_id"], "status": "pending"}


@app.get("/approval/status/{request_id}")
def get_status(request_id: str) -> dict:
    record = _get_or_404(request_id)
    return {
        "request_id": record["request_id"],
        "status": record["status"],
        "workflow_id": record["workflow_id"],
    }


@app.post("/approval/approve/{request_id}")
def approve(request_id: str) -> dict:
    return _set_status(request_id, "approved")


@app.post("/approval/reject/{request_id}")
def reject(request_id: str) -> dict:
    return _set_status(request_id, "rejected")


@app.post("/approval/auto-approve")
def auto_approve() -> dict:
    approved = [
        request_id
        for request_id, record in _requests.items()
        if record["status"] == "pending"
    ]
    for request_id in approved:
        _requests[request_id]["status"] = "approved"
    log.info("auto_approved", count=len(approved))
    return {"approved": approved}


@app.delete("/approval/requests")
def clear_requests() -> dict:
    count = len(_requests)
    _requests.clear()
    log.info("requests_cleared", count=count)
    return {"cleared": count}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
