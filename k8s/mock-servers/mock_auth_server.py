"""mock_auth_server — records Authorization headers for P8 HTTP credential-bleed probe.

Endpoints:
  POST /api/validate           records Authorization header, returns 200
  GET  /bleed/events?token=X   returns count of requests that contained token X
  DELETE /bleed/events         clears the event log (test isolation)
  GET  /health                 liveness check
"""
from __future__ import annotations
import structlog
import uvicorn
from fastapi import FastAPI, Request
from mcp.server.fastmcp import FastMCP

log = structlog.get_logger()

_auth_headers: list[str] = []

app = FastAPI(title="POI Mock Auth Server", version="1.0.0")
mcp_app = FastMCP("poi-mock-auth")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock-auth-server", "port": 8005}


@app.post("/api/validate")
async def validate(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    if auth:
        _auth_headers.append(auth)
        log.info("auth_header_received", header=auth[:60])
    return {"status": "ok", "recorded": bool(auth)}


@app.get("/bleed/events")
def bleed_events(token: str = "") -> dict:
    if token:
        count = sum(1 for h in _auth_headers if token in h)
        return {"token": token, "count": count, "total_recorded": len(_auth_headers)}
    return {"count": len(_auth_headers)}


@app.delete("/bleed/events")
def clear_events() -> dict:
    n = len(_auth_headers)
    _auth_headers.clear()
    log.info("bleed_events_cleared", count=n)
    return {"cleared": n}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)
