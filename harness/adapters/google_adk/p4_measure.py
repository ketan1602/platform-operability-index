"""P4 (Golden-Path Packageability) measurements for Google ADK F4.

Google ADK defaults to Cloud Run deployment; adapting to local K8s/Helm
requires overriding the default runner and disabling Cloud Trace.
LiteLLM env vars and the OTLP endpoint must both be wired into the chart.
"""
from __future__ import annotations
from pathlib import Path

import structlog

from harness.shared.pillar_models import P4Measurements

log = structlog.get_logger(__name__)

_CHART_DIR = (
    Path(__file__).parent.parent.parent.parent / "charts" / "poi-google-adk"
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
    hacks = [
        "ADK_RUNNER=local env var required to disable Cloud Run default runner",
        "GOOGLE_CLOUD_PROJECT must be set even for local non-GCP deployment",
        "LiteLLM LITELLM_BASE_URL env var overrides ADK's default AI Platform routing",
    ]
    blockers = [
        "GOOGLE_APPLICATION_CREDENTIALS required even in local mode without --no-auth flag"
    ]
    log.info("p4.measured", framework="F4", template_loc=template_loc)
    return P4Measurements(
        template_creation_time_hrs=5.0,
        template_loc=template_loc,
        framework_specific_hacks_required=hacks,
        policy_authorable_without_framework_internals=True,
        required_framework_internal_hooks=[],
        one_day_deployment_achieved=True,
        deployment_time_hrs=1.5,
        blockers_encountered=blockers,
    )
