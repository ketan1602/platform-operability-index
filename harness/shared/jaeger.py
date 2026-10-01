"""Read a run's spans back from Jaeger and measure trace quality for P3."""
from __future__ import annotations
import os
import time

import requests

REQUIRED = ("gen_ai.operation.name", "gen_ai.provider.name",
            "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens")
# gen_ai.system is the pre-1.37 semconv name for gen_ai.provider.name.
ALIASES = {"gen_ai.provider.name": ("gen_ai.provider.name", "gen_ai.system")}


def fetch_spans(service: str, settle_s: float = 4.0, timeout_s: float = 30.0) -> list[dict]:
    """Poll until the span count stops changing (batch export is asynchronous)."""
    base = os.environ.get("JAEGER_QUERY_URL", "")
    if not base:
        raise RuntimeError("JAEGER_QUERY_URL must be set (run ./infra.sh up)")
    deadline, last, stable_since = time.monotonic() + timeout_s, -1, time.monotonic()
    spans: list[dict] = []
    while time.monotonic() < deadline:
        r = requests.get(f"{base}/api/traces", params={"service": service, "limit": 500}, timeout=10)
        r.raise_for_status()
        spans = [s for t in r.json().get("data") or [] for s in t["spans"]]
        if len(spans) != last:
            last, stable_since = len(spans), time.monotonic()
        elif time.monotonic() - stable_since >= settle_s:
            break
        time.sleep(1)
    return spans


def _tags(span: dict) -> dict:
    return {t["key"]: t["value"] for t in span.get("tags", [])}


def _present(attrs: set[str]) -> list[str]:
    return [req for req in REQUIRED if any(a in attrs for a in ALIASES.get(req, (req,)))]


def _int_tag(tags: dict, key: str) -> int:
    val = tags.get(key)
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


def analyse(spans: list[dict], agent_names: list[str]) -> dict:
    ids = {s["spanID"] for s in spans}
    orphans = sum(
        1 for s in spans
        for ref in s.get("references", [])
        if ref.get("refType") == "CHILD_OF" and ref["spanID"] not in ids
    )
    all_tags = [_tags(s) for s in spans]
    attrs = {k for t in all_tags for k in t}
    text = " ".join(
        s["operationName"] + " " + " ".join(str(v) for v in t.values())
        for s, t in zip(spans, all_tags)
    ).lower()
    present = _present(attrs)
    total_input = sum(_int_tag(t, "gen_ai.usage.input_tokens") for t in all_tags)
    total_output = sum(_int_tag(t, "gen_ai.usage.output_tokens") for t in all_tags)
    return {
        "framework_spans": len(spans),
        "trace_ids_per_run": len({s["traceID"] for s in spans}),
        "orphan_spans": orphans,
        "required_attributes_emitted_by_default": present,
        "missing_required_attributes": [r for r in REQUIRED if r not in present],
        "agents_invoked": len(agent_names),
        "agents_traced": sum(1 for a in agent_names if a.lower() in text),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
    }
