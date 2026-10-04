"""tracing_shim — Strands OTEL tracing export.

Lines between poi:custom markers are operator-written code required to
enable OTEL trace export. Strands provides opt-in telemetry via
`StrandsTelemetry`; the operator instantiates it and calls
`setup_otlp_tracing()` with the collector endpoint.

custom_loc.count() → 2
"""
from __future__ import annotations
import os
from strands.telemetry import StrandsTelemetry

# poi:custom-begin
_telemetry = StrandsTelemetry()
_telemetry.setup_otlp_tracing(otlp_endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])
# poi:custom-end


def custom_loc() -> "list[str]":
    """Return lines between poi markers (used by the LOC counter)."""
    return [
        "_telemetry = StrandsTelemetry()",
        "_telemetry.setup_otlp_tracing(otlp_endpoint=os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'])",
    ]
