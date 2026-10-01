"""Liveness + readiness. Readiness doubles as the run preflight shown in the UI."""
from __future__ import annotations
import os
import socket
from urllib.parse import urlparse

import requests
from fastapi import APIRouter

from api.config import REPO_ROOT, missing_live_env

router = APIRouter()

_ADAPTER_DIRS = {"F1": "langgraph", "F2": "ms_agent", "F3": "openai_sdk", "F4": "google_adk", "F5": "strands"}
_HTTP_ENV = ("MOCK_API_URL", "MOCK_CRM_URL", "APPROVAL_URL", "ML_ENDPOINT_URL",
             "CHANNEL_ADAPTER_URL", "JAEGER_QUERY_URL")
_TCP_ENV = ("POSTGRES_URL", "RABBITMQ_URL", "NEO4J_URI")


def _venv_ready(adapter: str) -> bool:
    return (REPO_ROOT / "harness" / "adapters" / adapter / ".venv" / "bin" / "python").exists()


def _http(env_name: str) -> str:
    url = os.environ.get(env_name)
    if not url:
        return "unset"
    try:
        requests.get(url, timeout=1)
        return "up"
    except requests.RequestException:
        return "down"


def _tcp(env_name: str) -> str:
    url = os.environ.get(env_name)
    if not url:
        return "unset"
    parsed = urlparse(url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return "up"
    except OSError:
        return "down"


@router.get("/health")
def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> dict:
    missing = missing_live_env()
    services = {**{n: _http(n) for n in _HTTP_ENV}, **{n: _tcp(n) for n in _TCP_ENV}}
    frameworks = {fid: _venv_ready(d) for fid, d in _ADAPTER_DIRS.items()}
    ready = not missing and all(v == "up" for v in services.values()) and all(frameworks.values())
    return {
        "status": "ready" if ready else "degraded",
        "llm_env_missing": missing,
        "frameworks_installed": frameworks,
        "mock_services": services,
    }
