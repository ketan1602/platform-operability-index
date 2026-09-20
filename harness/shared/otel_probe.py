"""Probe Prometheus / OTel Collector for Pillar 3 measurements.

PROMETHEUS_URL is read from the environment at import time so adapters can
override it before importing this module.  All network calls swallow
exceptions and log warnings — a missing Prometheus is treated as "no data",
not a fatal error.
"""
from __future__ import annotations
import os
import time

import structlog

log = structlog.get_logger(__name__)

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

REQUIRED_OTEL_ATTRIBUTES = [
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
]

BONUS_OTEL_ATTRIBUTES = [
    "gen_ai.invoke_agent",
    "gen_ai.execute_tool",
    "gen_ai.invoke_workflow",
]


def _prom_query(query: str) -> list | None:
    """Execute a Prometheus instant query; return result list or None on error."""
    import requests  # noqa: PLC0415
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("result", [])
    except Exception as exc:
        log.warning("prom_query.failed", query=query, error=str(exc))
        return None


def spans_emitting(service_name: str, timeout_s: int = 30) -> bool:
    """Poll until spans from *service_name* appear in Prometheus or timeout."""
    deadline = time.monotonic() + timeout_s
    query = f'otelcol_receiver_accepted_spans{{service="{service_name}"}}'
    while time.monotonic() < deadline:
        result = _prom_query(query)
        if result:
            log.info("spans_emitting.detected", service=service_name)
            return True
        time.sleep(2)
    log.warning("spans_emitting.timeout", service=service_name, timeout_s=timeout_s)
    return False


def get_emitted_attributes(service_name: str, run_id: str) -> list[str]:
    """Return which OTel attributes (required + bonus) appear for this run."""
    found: list[str] = []
    for attr in REQUIRED_OTEL_ATTRIBUTES + BONUS_OTEL_ATTRIBUTES:
        query = f'count({{__name__=~".*",run_id="{run_id}",{attr}=~".+"}})'
        result = _prom_query(query)
        if result:
            found.append(attr)
    log.info("get_emitted_attributes.done", run_id=run_id, found=found)
    return found


def missing_required_attributes(emitted: list[str]) -> list[str]:
    """Return REQUIRED_OTEL_ATTRIBUTES not present in *emitted*."""
    return [a for a in REQUIRED_OTEL_ATTRIBUTES if a not in emitted]


def check_alert_fired(run_id: str, timeout_s: int = 120) -> tuple[bool, int | None]:
    """Poll until a Prometheus alert fires for *run_id* or timeout expires.

    Returns (fired, latency_ms).  latency_ms is None when no alert fired.
    """
    deadline = time.monotonic() + timeout_s
    start = time.monotonic()
    query = f'ALERTS{{run_id="{run_id}",alertstate="firing"}}'
    while time.monotonic() < deadline:
        result = _prom_query(query)
        if result:
            latency_ms = int((time.monotonic() - start) * 1000)
            log.info("alert.fired", run_id=run_id, latency_ms=latency_ms)
            return True, latency_ms
        time.sleep(3)
    log.warning("alert.not_fired", run_id=run_id, timeout_s=timeout_s)
    return False, None
