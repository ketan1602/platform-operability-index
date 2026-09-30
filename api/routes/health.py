"""Liveness + readiness. Readiness doubles as the live-run preflight shown in the UI."""
from __future__ import annotations
import importlib.util
import os

import requests
from fastapi import APIRouter

from api.config import missing_live_env

router = APIRouter()

_FRAMEWORK_MODULES = {
    "F1": "langgraph",
    "F2": "autogen_agentchat",
    "F3": "agents",
    "F4": "google.adk",
    "F5": "strands",
}
_MOCK_URL_ENV = (
    "MOCK_API_URL", "MOCK_CRM_URL", "APPROVAL_URL",
    "NEO4J_STUB_URL", "ML_ENDPOINT_URL", "CHANNEL_ADAPTER_URL",
)


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def _reachable(env_name: str) -> str:
    url = os.environ.get(env_name)
    if not url:
        return "unset"
    try:
        requests.get(url, timeout=1)
        return "up"
    except requests.RequestException:
        return "down"


@router.get("/health")
def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> dict:
    missing = missing_live_env()
    frameworks = {fid: _installed(m) for fid, m in _FRAMEWORK_MODULES.items()}
    mocks = {name: _reachable(name) for name in _MOCK_URL_ENV}
    live_ready = not missing and all(v == "up" for v in mocks.values())
    return {
        "status": "ready" if live_ready else "degraded",
        "llm_env_missing": missing,
        "frameworks_installed": frameworks,
        "mock_services": mocks,
    }
