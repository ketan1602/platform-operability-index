"""Child-side SMA trial: standard OTel setup around one supervisor run."""
from __future__ import annotations
import asyncio
import importlib
import inspect

from harness.scenarios.common import impl_module
from harness.shared import tracing


def run(fw: str, service: str, **_) -> dict:
    provider = tracing.setup(service)
    try:
        result = importlib.import_module(impl_module("SMA", fw)).run()
        return asyncio.run(result) if inspect.iscoroutine(result) else result
    finally:
        tracing.shutdown(provider)
