"""TCW measurement: trace quality (P3) and failure containment (P2).

Trial A (healthy): runs TCW end-to-end with OTel and reads spans from Jaeger.
Trial B (faulty): POI_TCW_FAULT=1 causes score_propensity to raise; checks whether
the run crashes, hangs, or the framework contains the fault.

TCW has three instrumented service calls (graph query, ML score, channel dispatch),
making it a richer second P3 data point alongside SMA.
"""
from __future__ import annotations
import uuid

from harness.scenarios.common import TrialError, env_int, workdir
from harness.shared import child, jaeger, ledger
from harness.shared.pillar_models import P2Measurements, P3Measurements

_TIMEOUT = "POI_TCW_TIMEOUT_S"
_OUTCOME = {"timeout": "hung", "ceiling": "hung"}

_TCW_STEPS = [
    "step1_graph_query",
    "step2_propensity_score",
    "step3_eligibility_check",
    "step4_offer_personalize",
    "step5_channel_dispatch",
]


def _trial(fw: str, fault: bool) -> tuple[child.Outcome, list[dict], str]:
    path = workdir("TCW-P2P3") / "ledger.jsonl"
    service = f"poi-{fw.lower()}-tcw-{uuid.uuid4().hex[:8]}"
    env = {"POI_TCW_FAULT": "1" if fault else "0"}
    proc = child.spawn(
        "harness.scenarios.tcw_trial:run",
        {"fw": fw, "service": service},
        path,
        env,
    )
    out = child.watch(proc, path, timeout_s=env_int(_TIMEOUT, 600))
    return out, ledger.read(path), service


def _propagation(out: child.Outcome) -> str:
    if out.stop in _OUTCOME:
        return _OUTCOME[out.stop]
    return "contained" if (out.result or {}).get("stop") == "final_answer" else "crashed_run"


def measure(fw: str) -> dict:
    healthy, entries, service = _trial(fw, fault=False)
    if (healthy.result or {}).get("stop") != "final_answer":
        raise TrialError(f"TCW {fw} healthy trial failed: {healthy.stop} {healthy.result}")

    spans = jaeger.fetch_spans(service)
    trace = jaeger.analyse(spans, _TCW_STEPS)

    faulty, f_entries, _ = _trial(fw, fault=True)
    prop = _propagation(faulty)
    non_ml = ["tcw_graph_queried", "tcw_channel_dispatched"]
    siblings = sum(1 for ev in non_ml if ledger.count(f_entries, ev) > 0)
    detail = (
        (faulty.result or {}).get("signal")
        or (faulty.result or {}).get("stop")
        or faulty.stop
    )
    notes = (
        f"fault trial: {prop} ({detail}); "
        f"healthy trial spans: {trace['framework_spans']}"
    )
    return {
        "notes": notes,
        "p3": P3Measurements(
            **trace,
            custom_exporter_required=False,
            oss_stack_viable=trace["framework_spans"] > 0,
        ),
        "p2": P2Measurements(
            failure_propagation=prop,
            sibling_agents_completed=siblings,
        ),
    }
