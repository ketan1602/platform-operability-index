"""P2 (Blast-Radius Containment) measurements for Strands Agents F5.

Strands Agent accepts a max_iterations parameter but defaults to None (unlimited).
Without max_iterations a runaway tool-calling loop runs until the model stops.
Setting max_iterations requires explicit configuration (2 lines of custom code).
Credential bleed: OpenAIModel client is per-Agent instance; no cross-agent leakage.
"""
from __future__ import annotations
from pathlib import Path

import structlog

from harness.shared import custom_loc
from harness.shared.pillar_models import P2Measurements

log = structlog.get_logger(__name__)

_SHIM_PY = Path(__file__).parent / "isolation_shim.py"


def measure_p2() -> P2Measurements:
    isolation_loc = custom_loc.count(_SHIM_PY)
    log.info(
        "p2.measured",
        framework="F5",
        contained=False,
        kill_switch="platform_sigterm",
        isolation_loc=isolation_loc,
    )
    return P2Measurements(
        runaway_loop_contained_by_default=False,
        time_to_framework_halt_ms=None,
        credential_bleed_events=0,
        kill_switch_type="platform_sigterm",
        halt_latency_ms=None,
        halt_signal=None,
        isolation_requires_custom_code=True,
        custom_code_lines_for_isolation=isolation_loc,
    )
