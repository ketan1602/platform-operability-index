"""P4 (Golden-Path Packageability) measurements for OpenAI Agents SDK F3.

The SDK requires a valid OpenAI-compatible base_url and API key (AI Refinery).
No checkpoint concept — simpler Helm template than LangGraph.
Non-standard base_url must be configured at deploy time (an env var).
"""
from __future__ import annotations
from pathlib import Path

import structlog

from harness.adapters.shared.k8s_fit import test_lazy_init, test_sigterm
from harness.scenarios.dx_extras import count_hitl_loc, run_hitl
from harness.shared.p4_chart import probe_chart_hacks

_FW_ID = "F3"
from harness.shared.pillar_models import HackRecord, P4Measurements

log = structlog.get_logger(__name__)

_CORE_MODULE = "agents"

_CHART_DIR = (
    Path(__file__).parent.parent.parent.parent / "charts" / "poi-openai-sdk"
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
            description="AIREFINERY_BASE_URL must be set; SDK defaults to api.openai.com",
            cost_hrs=1.0, recurring_hrs_per_yr=0.5,
        ),
        HackRecord(
            description="set_trace_processor() call must be added to container entrypoint",
            cost_hrs=1.0, recurring_hrs_per_yr=1.0, upgrade_sensitive=True,
        ),
    ]
    lazy_s, lazy_ms = test_lazy_init(_CORE_MODULE)
    sigterm_ok, sigterm_ms = test_sigterm(_CORE_MODULE)
    pod_hacks = probe_chart_hacks(_CHART_DIR)
    log.info("p4.measured", framework="F3", template_loc=template_loc,
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
