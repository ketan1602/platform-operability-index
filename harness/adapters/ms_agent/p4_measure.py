"""P4 (Golden-Path Packageability) measurements for AutoGen F2.

Counts template LOC from charts/poi-ms-agent/.  AutoGen has no checkpoint
concept so CHECKPOINT_BACKEND_URL is omitted — one fewer framework-specific
env var to wire up vs LangGraph.
"""
from __future__ import annotations
from pathlib import Path

import structlog

from harness.adapters.shared.k8s_fit import test_lazy_init, test_sigterm
from harness.scenarios.dx_extras import count_hitl_loc, run_hitl
from harness.shared.p4_chart import probe_chart_hacks

_FW_ID = "F2"
from harness.shared.pillar_models import HackRecord, P4Measurements

log = structlog.get_logger(__name__)

_CORE_MODULE = "autogen_agentchat"

_CHART_DIR = (
    Path(__file__).parent.parent.parent.parent / "charts" / "poi-ms-agent"
)


def _count_template_loc() -> int:
    if not _CHART_DIR.exists():
        return 0
    return sum(
        1
        for f in _CHART_DIR.rglob("*.yaml")
        for ln in f.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )


def measure_p4() -> P4Measurements:
    template_loc = _count_template_loc()
    hitl_works, hitl_gate_ms = run_hitl(_FW_ID)
    hacks = [
        HackRecord(
            description="max_turns must be set per-agent; no cluster-wide policy primitive for this",
            cost_hrs=0.5, recurring_hrs_per_yr=0.5,
        ),
        HackRecord(
            description="autogen-ext[opentelemetry] must be pip-installed separately in image",
            cost_hrs=1.0, recurring_hrs_per_yr=0.5, upgrade_sensitive=True,
        ),
    ]
    lazy_s, lazy_ms = test_lazy_init(_CORE_MODULE)
    sigterm_ok, sigterm_ms = test_sigterm(_CORE_MODULE)
    pod_hacks = probe_chart_hacks(_CHART_DIR)
    log.info("p4.measured", framework="F2", template_loc=template_loc,
             lazy_init_s=lazy_s, sigterm_graceful=sigterm_ok, pod_hacks=pod_hacks)
    return P4Measurements(
        template_loc=template_loc,
        framework_specific_hacks_required=hacks,
        policy_authorable_without_framework_internals=True,
        required_framework_internal_hooks=[],
        one_day_deployment_achieved=True,
        blockers_encountered=[],
        lazy_init_s=lazy_s,
        lazy_init_ms=lazy_ms,
        sigterm_graceful=sigterm_ok,
        sigterm_latency_ms=sigterm_ms,
        hitl_gate_loc=count_hitl_loc(_FW_ID),
        hitl_gate_latency_ms=hitl_gate_ms,
        hitl_native=False,
        hitl_verified=hitl_works,
        hacks_detected_in_pod=pod_hacks,
    )
