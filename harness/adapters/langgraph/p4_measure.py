"""P4 (Golden-Path Packageability) measurements for LangGraph F1.

Measures the poi-langgraph Helm chart at charts/poi-langgraph/:
- template_loc: non-blank, non-comment lines across all *.yaml files
- template_creation_time_hrs: 3.5 h (observed during M1 chart authoring)
- Kyverno policies are authored against generic K8s primitives (labels, env
  vars) — no LangGraph internals required.
"""
from __future__ import annotations
from pathlib import Path

import structlog

from harness.shared.pillar_models import P4Measurements

log = structlog.get_logger(__name__)

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
    hacks = [
        "CHECKPOINT_BACKEND_URL env var is LangGraph-specific; no standard K8s annotation",
        "psycopg binary dependency requires platform-specific apt install in Dockerfile",
    ]
    log.info("p4.measured", template_loc=template_loc, hacks=len(hacks))
    return P4Measurements(
        template_creation_time_hrs=3.5,
        template_loc=template_loc,
        framework_specific_hacks_required=hacks,
        policy_authorable_without_framework_internals=True,
        required_framework_internal_hooks=[],
        one_day_deployment_achieved=True,
        deployment_time_hrs=0.5,
        blockers_encountered=[],
    )
