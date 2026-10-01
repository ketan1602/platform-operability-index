"""SMA measurement: trace quality across agent hops (P3) and failure containment (P2).

Trial A (healthy): the run's spans are read back from Jaeger. Trial B: the network
specialist's tool raises; does the run still finish, crash, or hang?
"""
from __future__ import annotations
import uuid

from harness.scenarios.common import TrialError, env_int, impl_path, impl_target, workdir
from harness.shared import child, custom_loc, jaeger, ledger
from harness.shared.pillar_models import P2Measurements, P3Measurements
from scenarios.sma.shared.tools import SPECIALISTS, SUPERVISOR, TOOL_EVENTS

_OUTCOME = {"timeout": "hung", "ceiling": "hung"}


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


def measure(fw: str) -> dict:
    healthy, entries, service = _trial(fw, fault=False)
    if (healthy.result or {}).get("stop") != "final_answer":
        raise TrialError(f"SMA {fw} healthy trial failed: {healthy.stop} {healthy.result}")
    trace = jaeger.analyse(jaeger.fetch_spans(service), _invoked(entries))
    glue = custom_loc.count(impl_path("SMA", fw))
    faulty, f_entries, _ = _trial(fw, fault=True)
    siblings = [s for s in SPECIALISTS if s != "network_agent" and ledger.count(f_entries, TOOL_EVENTS[s])]
    detail = (faulty.result or {}).get("signal") or (faulty.result or {}).get("stop") or faulty.stop
    return {
        "notes": f"fault trial: {_propagation(faulty)} ({detail}); healthy trial spans: {trace['framework_spans']}",
        "p3": P3Measurements(**trace, custom_exporter_loc=glue, custom_exporter_required=glue > 0,
                             oss_stack_viable=trace["framework_spans"] > 0),
        "p2": P2Measurements(failure_propagation=_propagation(faulty),
                             sibling_agents_completed=len(siblings)),
    }
