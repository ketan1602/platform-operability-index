"""tracing_shim — OpenAI Agents SDK OTEL tracing export.

Lines between poi:custom markers are operator-written code required to
enable OTEL trace export. The OpenAI Agents SDK provides
`agents.set_trace_processor()`; the operator must instantiate the OTLP
exporter and register it.

custom_loc.count() → 2
"""
from __future__ import annotations
import os
import agents
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# poi:custom-begin
_exporter = OTLPSpanExporter(endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])
agents.set_trace_processor(_exporter)
# poi:custom-end


def custom_loc() -> "list[str]":
    """Return lines between poi markers (used by the LOC counter)."""
    return [
        "_exporter = OTLPSpanExporter(endpoint=os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'])",
        "agents.set_trace_processor(_exporter)",
    ]
