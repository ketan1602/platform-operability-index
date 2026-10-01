"""Standard platform OTel setup: a global TracerProvider exporting OTLP/HTTP.

This is what any platform team configures once per service. Frameworks that emit
OpenTelemetry natively pick it up automatically; frameworks that don't, emit nothing.
Nothing framework-specific is registered here.
"""
from __future__ import annotations
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup(service_name: str) -> TracerProvider:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        raise RuntimeError("OTEL_EXPORTER_OTLP_ENDPOINT must be set (run ./infra.sh up)")
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    trace.set_tracer_provider(provider)
    return provider


def shutdown(provider: TracerProvider) -> None:
    provider.force_flush()
    provider.shutdown()
