"""P3 (Observability-Nativeness) measurements for LangGraph F1.

LangGraph integrates with OTel via langchain-opentelemetry (community package,
not bundled by default).  Required gen_ai.* token-count attributes are absent
in many versions (token usage flows through callbacks, not span attributes).
Prometheus probe attempted if PROMETHEUS_URL is set; falls back to desk-research
values otherwise.
"""
from __future__ import annotations
import os
from pathlib import Path

import structlog

from harness.shared import custom_loc
from harness.shared.otel_probe import (
    REQUIRED_OTEL_ATTRIBUTES,
    get_emitted_attributes,
    spans_emitting,
)
from harness.shared.pillar_models import P3Measurements

log = structlog.get_logger(__name__)

_KNOWN_MISSING = ["gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"]


def _probe_prometheus(run_id: str) -> list[str]:
    if not os.environ.get("PROMETHEUS_URL", ""):
        log.info("p3.prom_skipped", reason="PROMETHEUS_URL not set")
        return []
    alive = spans_emitting("poi-langgraph", timeout_s=15)
    if not alive:
        log.warning("p3.no_spans_detected", service="poi-langgraph")
        return []
    return get_emitted_attributes("poi-langgraph", run_id)


def measure_p3(run_id: str = "p3-probe-f1") -> P3Measurements:
    emitted = _probe_prometheus(run_id)
    if emitted:
        missing = [a for a in REQUIRED_OTEL_ATTRIBUTES if a not in emitted]
    else:
        missing = _KNOWN_MISSING
        emitted = [a for a in REQUIRED_OTEL_ATTRIBUTES if a not in missing]

    loc = custom_loc.count(Path(__file__).parent / "tracing_shim.py")
    log.info("p3.measured", emitted=emitted, missing=missing, exporter_loc=loc)
    return P3Measurements(
        required_attributes_emitted_by_default=emitted,
        missing_required_attributes=missing,
        alert_fired_without_custom_code=False,
        alert_latency_ms=None,
        custom_exporter_required=loc > 0,
        custom_exporter_loc=loc,
        proprietary_backend_required=False,
        oss_stack_viable=True,
    )
