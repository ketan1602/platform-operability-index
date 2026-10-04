"""tracing_shim — Google ADK OTEL tracing export.

Lines between poi:custom markers are operator-written code required to
enable OTEL trace export. ADK has no native OTEL export path. The operator
must build a full TracerProvider, attach an OTLPSpanExporter, get a named
tracer, and wrap the runner invocation in a custom span with gen_ai.*
semantic-convention attributes.

custom_loc.count() → 9
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
_tracer = trace.get_tracer("google_adk.poi")


def run_with_span(runner, session, prompt: str):
    with _tracer.start_as_current_span("adk.run") as span:
        span.set_attribute("gen_ai.system", "google_adk")
        span.set_attribute("gen_ai.request.model", os.environ.get("MODEL_ID", "unknown"))
        return runner.run(session=session, message=prompt)
# poi:custom-end


def custom_loc() -> "list[str]":
    """Return lines between poi markers (used by the LOC counter)."""
    return [
        "_provider = TracerProvider()",
        "_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(...)))",
        "trace.set_tracer_provider(_provider)",
        '_tracer = trace.get_tracer("google_adk.poi")',
        "def run_with_span(runner, session, prompt):",
        '    with _tracer.start_as_current_span("adk.run") as span:',
        '        span.set_attribute("gen_ai.system", "google_adk")',
        '        span.set_attribute("gen_ai.request.model", os.environ.get(...))',
        "        return runner.run(session=session, message=prompt)",
    ]
