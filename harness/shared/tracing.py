"""Standard platform OTel setup: a global TracerProvider exporting OTLP/HTTP.

This is what any platform team configures once per service. Frameworks that emit
OpenTelemetry natively pick it up automatically; frameworks that don't, emit nothing.
Nothing framework-specific is registered here.

Always adds an InMemorySpanExporter so callers can inspect captured spans after the
run regardless of whether a remote OTLP collector is available. OTLP export is
added on top when OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""
from __future__ import annotations
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def setup(service_name: str) -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return (provider, in_memory_exporter).  OTLP is added when env var is set."""
    mem = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(mem))
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
        )
    trace.set_tracer_provider(provider)
    return provider, mem


def shutdown(provider: TracerProvider) -> None:
    provider.force_flush()
    provider.shutdown()
