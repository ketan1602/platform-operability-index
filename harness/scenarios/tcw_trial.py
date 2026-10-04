"""Child-side TCW trial: standard OTel setup around one TCW workflow run.

run() sets up a service-named OTel TracerProvider (so Jaeger receives spans under a
unique service name for this trial), invokes run_workflow(), shuts the provider down,
and returns a stop-keyed result so the parent can detect success vs. failure.
"""
from __future__ import annotations
import asyncio
import importlib
import inspect

from harness.scenarios.common import impl_module
from harness.shared import tracing


def run(fw: str, service: str, customer_id: str = "cust-001", **_) -> dict:
    provider, _ = tracing.setup(service)
    try:
        mod = importlib.import_module(impl_module("TCW", fw))
        result = mod.run_workflow(service, customer_id=customer_id)
        if inspect.iscoroutine(result):
            asyncio.run(result)
        return {"stop": "final_answer"}
    finally:
        tracing.shutdown(provider)
