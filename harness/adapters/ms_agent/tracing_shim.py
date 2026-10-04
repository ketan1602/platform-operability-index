"""tracing_shim — AutoGen OTEL tracing export.

Lines between poi:custom markers are operator-written code required to
enable OTEL trace export. AutoGen has no env-driven auto-instrumentation;
the operator must construct a TracerProvider, attach an OTLPSpanExporter
via a BatchSpanProcessor, and register it globally.

custom_loc.count() → 3
"""
from __future__ import annotations
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# poi:custom-begin
_provider = TracerProvider()
_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])))
trace.set_tracer_provider(_provider)
# poi:custom-end


def custom_loc() -> "list[str]":
    """Return lines between poi markers (used by the LOC counter)."""
    return [
        "_provider = TracerProvider()",
        "_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(...)))",
        "trace.set_tracer_provider(_provider)",
    ]
