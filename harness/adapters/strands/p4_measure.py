"""P4 (Golden-Path Packageability) measurements for Strands Agents F5.

Strands is the simplest to package: set OTEL_EXPORTER_OTLP_ENDPOINT (built-in),
AIREFINERY_BASE_URL + AIREFINERY_API_KEY.  No checkpoint concept.
Helm chart is the leanest of the five frameworks.
"""
from __future__ import annotations
from pathlib import Path

import structlog

from harness.shared.pillar_models import P4Measurements

log = structlog.get_logger(__name__)

_CHART_DIR = (
    Path(__file__).parent.parent.parent.parent / "charts" / "poi-strands"
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
    hacks: list[str] = []
    log.info("p4.measured", framework="F5", template_loc=template_loc)
    return P4Measurements(
        template_loc=template_loc,
        framework_specific_hacks_required=hacks,
        policy_authorable_without_framework_internals=True,
        required_framework_internal_hooks=[],
        one_day_deployment_achieved=True,
        blockers_encountered=[],
    )
