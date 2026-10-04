"""Child-side SMA trial: standard OTel setup around one supervisor run.

Captured in-process spans are serialised into the result so the parent can run
P3 analysis even when Jaeger is unavailable.
"""
from __future__ import annotations
import asyncio
import importlib
import inspect

from harness.scenarios.common import impl_module
from harness.shared import tracing


def _serialise_spans(exporter) -> list[dict]:
    result = []
    for s in exporter.get_finished_spans():
        result.append({
            "name": s.name,
            "trace_id": format(s.context.trace_id, "032x"),
            "span_id": format(s.context.span_id, "016x"),
            "parent_span_id": format(s.parent.span_id, "016x") if s.parent else None,
            "attributes": dict(s.attributes or {}),
        })
    return result


def run(fw: str, service: str, **_) -> dict:
    provider, exporter = tracing.setup(service)
    try:
        raw = importlib.import_module(impl_module("SMA", fw)).run()
        result = asyncio.run(raw) if inspect.iscoroutine(raw) else raw
    finally:
        tracing.shutdown(provider)
    spans = _serialise_spans(exporter)
    if isinstance(result, dict):
        result["_spans"] = spans
    return result
