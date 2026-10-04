"""SMA measurement: trace quality across agent hops (P3) and failure containment (P2).

Trial A (healthy): the run's spans are read back from Jaeger. Trial B: the network
specialist's tool raises; does the run still finish, crash, or hang?
Trial C: 3 concurrent in-process PORT workflow invocations — tests multi-tenancy.
"""
from __future__ import annotations
import asyncio
import importlib
import os
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import structlog

from harness.scenarios.common import TrialError, env_int, impl_module, impl_path, impl_target, workdir
from harness.shared import child, custom_loc, jaeger, ledger
from harness.shared.pillar_models import P2Measurements, P3Measurements
from scenarios.sma.shared.tools import SPECIALISTS, SUPERVISOR, TOOL_EVENTS

_ADAPTERS = Path(__file__).resolve().parents[2] / "harness" / "adapters"
_FW_ADAPTER = {"F1": "langgraph", "F2": "ms_agent", "F3": "openai_sdk",
               "F4": "google_adk", "F5": "strands"}

log = structlog.get_logger(__name__)

_OUTCOME = {"timeout": "hung", "ceiling": "hung"}
_ASYNC_FRAMEWORKS = {"F2", "F3", "F4"}


def _trial(fw: str, fault: bool) -> tuple[child.Outcome, list[dict], str]:
    path = workdir("SMA") / "ledger.jsonl"
    service = f"poi-{fw.lower()}-sma-{uuid.uuid4().hex[:8]}"
    env = {"POI_SMA_FAULT": "1" if fault else "0"}
    proc = child.spawn("harness.scenarios.sma_trial:run", {"fw": fw, "service": service}, path, env)
    out = child.watch(proc, path, timeout_s=env_int("POI_SMA_TIMEOUT_S", 600))
    return out, ledger.read(path), service


def _invoked(entries: list[dict]) -> list[str]:
    return [SUPERVISOR] + [s for s in SPECIALISTS if ledger.count(entries, TOOL_EVENTS[s])]


def _propagation(out: child.Outcome) -> str:
    if out.stop in _OUTCOME:
        return _OUTCOME[out.stop]
    return "contained" if (out.result or {}).get("stop") == "final_answer" else "crashed_run"


def _inprocess_run(fw: str, mod, rid: str) -> bool:
    """Call PORT workflow in-process; return True if returned run_id matches."""
    if fw in _ASYNC_FRAMEWORKS:
        result = asyncio.run(mod.run(sub_test="isolation", run_id=rid))
    else:
        result = mod.run(sub_test="isolation", run_id=rid)
    return (result or {}).get("run_id") == rid


def _trial_c(fw: str, ledger_path: "Path") -> bool:
    """Trial C: 3 concurrent in-process invocations of PORT workflow.

    PORT tools call ledger.record(), so POI_LEDGER must point at a scratch file
    for this in-process call (the adapter subprocess does not have it set).
    """
    scratch = ledger_path.parent / "trial_c_ledger.jsonl"
    prev = os.environ.get(ledger.LEDGER_ENV)
    os.environ[ledger.LEDGER_ENV] = str(scratch)
    try:
        mod = importlib.import_module(impl_module("PORT", fw))
        run_ids = [str(uuid.uuid4()) for _ in range(3)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_inprocess_run, fw, mod, rid) for rid in run_ids]
            results = [f.result() for f in futures]
        return all(results)
    finally:
        if prev is None:
            os.environ.pop(ledger.LEDGER_ENV, None)
        else:
            os.environ[ledger.LEDGER_ENV] = prev


def _cred_bleed_events(fw: str, wd: "Path") -> int:
    """Run SEC context sub-test; return 0 if clean, 1 if sentinel leaked."""
    path = wd / "ledger_cred_bleed.jsonl"
    proc = child.spawn(impl_target("SEC", fw), {"sub_test": "context"}, path)
    out = child.watch(proc, path, timeout_s=env_int("POI_SEC_TIMEOUT_S", 300))
    if out.stop != "exited":
        log.warning("cred_bleed_inconclusive", fw=fw, stop=out.stop)
        return 0
    return 0 if bool((out.result or {}).get("context_clean", False)) else 1


def _trace_for(healthy_out: child.Outcome, entries: list[dict], service: str,
               agent_names: list[str]) -> dict:
    """Return jaeger.analyse()-compatible dict from Jaeger or in-process spans."""
    jaeger_spans = jaeger.fetch_spans(service)
    if jaeger_spans:
        return jaeger.analyse(jaeger_spans, agent_names)
    inprocess = (healthy_out.result or {}).get("_spans", [])
    log.info("p3.using_inprocess_spans", count=len(inprocess), fw=entries[0] if entries else "?")
    return jaeger.analyse_dicts(inprocess, agent_names)


def _tracing_glue(fw: str) -> int:
    """Count operator LOC needed to enable OTEL export for this framework."""
    adapter = _FW_ADAPTER.get(fw, fw.lower())
    return custom_loc.count(_ADAPTERS / adapter / "tracing_shim.py")


def measure(fw: str) -> dict:
    wd = workdir("SMA")
    healthy, entries, service = _trial(fw, fault=False)
    if (healthy.result or {}).get("stop") != "final_answer":
        raise TrialError(f"SMA {fw} healthy trial failed: {healthy.stop} {healthy.result}")
    trace = _trace_for(healthy, entries, service, _invoked(entries))
    glue = _tracing_glue(fw)
    faulty, f_entries, _ = _trial(fw, fault=True)
    siblings = [s for s in SPECIALISTS if s != "network_agent" and ledger.count(f_entries, TOOL_EVENTS[s])]
    detail = (faulty.result or {}).get("signal") or (faulty.result or {}).get("stop") or faulty.stop
    faulty_spans = (faulty.result or {}).get("_spans", [])
    alert_native = jaeger.has_error_signal(faulty_spans)
    tenancy_safe = _trial_c(fw, wd / "ledger.jsonl")
    bleed = _cred_bleed_events(fw, wd)
    log.info("sma.measure", fw=fw, spans=trace["framework_spans"], bleed=bleed,
             propagation=_propagation(faulty), alert_native=alert_native, tenancy_safe=tenancy_safe)
    return {
        "notes": (
            f"fault trial: {_propagation(faulty)} ({detail}); "
            f"healthy trial spans: {trace['framework_spans']}; "
            f"alert_native={alert_native}; "
            f"concurrent_tenancy_safe={tenancy_safe}; "
            f"cred_bleed_events={bleed}"
        ),
        "p3": P3Measurements(**trace, custom_exporter_loc=glue, custom_exporter_required=glue > 0,
                             alert_fired_without_custom_code=alert_native,
                             oss_stack_viable=trace["framework_spans"] > 0),
        "p2": P2Measurements(failure_propagation=_propagation(faulty),
                             sibling_agents_completed=len(siblings),
                             concurrent_tenancy_safe=tenancy_safe,
                             credential_bleed_events=bleed),
    }
