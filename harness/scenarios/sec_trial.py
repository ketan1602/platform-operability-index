"""Child-side SEC secret-leakage trial: optional OTel setup around run_secret.

Mirrors sma_trial.py: sets up a TracerProvider so framework spans are exported
to Jaeger if OTEL_EXPORTER_OTLP_ENDPOINT is configured, then delegates to the
framework's run_secret function.
"""
from __future__ import annotations
import asyncio
import importlib
import inspect
import os

from harness.scenarios.common import impl_module
from harness.shared import tracing


def run_secret(fw: str, service: str, **_) -> dict:
    """Set up OTel (when available) and run the framework's run_secret."""
    has_otel = bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
    provider = tracing.setup(service) if has_otel else None
    try:
        mod = importlib.import_module(impl_module("SEC", fw))
        result = mod.run_secret()
        return asyncio.run(result) if inspect.iscoroutine(result) else result
    finally:
        if provider:
            tracing.shutdown(provider)
