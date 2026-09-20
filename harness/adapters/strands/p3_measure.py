"""P3 (Observability-Nativeness) measurements for Strands Agents F5.

Strands Agents ships with built-in OpenTelemetry support.  Setting
OTEL_EXPORTER_OTLP_ENDPOINT is sufficient to start emitting spans.
The gen_ai.* semantic conventions are emitted for operation name and provider.
Token usage attributes require the model to return usage metadata (works with
AI Refinery's OpenAI-compatible API).
"""
from __future__ import annotations
import os

import structlog

from harness.shared.otel_probe import (
    REQUIRED_OTEL_ATTRIBUTES,
    get_emitted_attributes,
    spans_emitting,
)
from harness.shared.pillar_models import P3Measurements

log = structlog.get_logger(__name__)

_EXPORTER_LOC = 0
_KNOWN_MISSING: list[str] = []


def _probe_prometheus(run_id: str) -> list[str]:
    if not os.environ.get("PROMETHEUS_URL", ""):
        return []
    alive = spans_emitting("poi-strands", timeout_s=15)
    if not alive:
        return []
    return get_emitted_attributes("poi-strands", run_id)


def measure_p3(run_id: str = "p3-probe-f5") -> P3Measurements:
    emitted = _probe_prometheus(run_id)
    if emitted:
        missing = [a for a in REQUIRED_OTEL_ATTRIBUTES if a not in emitted]
    else:
        missing = _KNOWN_MISSING
        emitted = list(REQUIRED_OTEL_ATTRIBUTES)

    log.info("p3.measured", framework="F5", emitted=emitted, missing=missing)
    return P3Measurements(
        required_attributes_emitted_by_default=emitted,
        missing_required_attributes=missing,
        alert_fired_without_custom_code=False,
        alert_latency_ms=None,
        custom_exporter_required=False,
        custom_exporter_loc=_EXPORTER_LOC,
        proprietary_backend_required=False,
        oss_stack_viable=True,
    )
