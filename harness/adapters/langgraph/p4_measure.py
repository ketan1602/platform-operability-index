"""P4 (Golden-Path Packageability) measurements for LangGraph F1.

Measures the poi-langgraph Helm chart at charts/poi-langgraph/:
- template_loc: non-blank, non-comment lines across all *.yaml files (counted in code)
- framework_specific_hacks_required: K8s workarounds documented below
- Kyverno policies are authored against generic K8s primitives (labels, env
  vars) — no LangGraph internals required.
"""
from __future__ import annotations
from pathlib import Path

import structlog

from harness.adapters.shared.k8s_fit import test_lazy_init, test_sigterm
from harness.scenarios.dx_extras import count_hitl_loc, run_hitl
from harness.shared.p4_chart import probe_chart_hacks

_FW_ID = "F1"
from harness.shared.pillar_models import HackRecord, P4Measurements

log = structlog.get_logger(__name__)

_CORE_MODULE = "langgraph"

_CHART_DIR = (
    Path(__file__).parent.parent.parent.parent / "charts" / "poi-langgraph"
)


def _count_template_loc() -> int:
    total = 0
    for f in _CHART_DIR.rglob("*.yaml"):
        lines = [
            ln for ln in f.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        total += len(lines)
    return total


def measure_p4() -> P4Measurements:
    template_loc = _count_template_loc()
    hitl_works, hitl_gate_ms = run_hitl(_FW_ID)
    hacks = [
        HackRecord(
            description="CHECKPOINT_BACKEND_URL env var is LangGraph-specific; no standard K8s annotation",
            cost_hrs=1.0, recurring_hrs_per_yr=0.5, upgrade_sensitive=True,
        ),
        HackRecord(
            description="psycopg binary dependency requires platform-specific apt install in Dockerfile",
            cost_hrs=2.0, recurring_hrs_per_yr=1.0, upgrade_sensitive=True,
        ),
    ]
    lazy_s, lazy_ms = test_lazy_init(_CORE_MODULE)
    sigterm_ok, sigterm_ms = test_sigterm(_CORE_MODULE)
    pod_hacks = probe_chart_hacks(_CHART_DIR)
    log.info("p4.measured", template_loc=template_loc, hacks=len(hacks),
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
        hitl_native=True,
        hitl_verified=hitl_works,
        hacks_detected_in_pod=pod_hacks,
    )
