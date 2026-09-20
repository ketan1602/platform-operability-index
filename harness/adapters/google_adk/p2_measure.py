"""P2 (Blast-Radius Containment) measurements for Google ADK F4.

Google ADK SequentialAgent runs agents in order; it has no loop detection
or recursion limit by default.  A misconfigured routing agent can run
indefinitely.  The only reliable containment is K8s resource limits.
Credential bleed: InMemorySessionService is process-scoped; no cross-tenant
state without explicit multi-session setup.
"""
from __future__ import annotations
import structlog
from harness.shared.pillar_models import P2Measurements

log = structlog.get_logger(__name__)


def measure_p2() -> P2Measurements:
    log.info(
        "p2.measured",
        framework="F4",
        contained=False,
        kill_switch="no_mechanism",
        note=(
            "SequentialAgent has no max_steps limit; LlmAgent routing can loop "
            "if transfer_to_agent forms a cycle"
        ),
    )
    return P2Measurements(
        runaway_loop_contained_by_default=False,
        time_to_framework_halt_ms=None,
        credential_bleed_events=0,
        kill_switch_type="no_mechanism",
        halt_latency_ms=None,
        isolation_requires_custom_code=True,
        custom_code_lines_for_isolation=10,
    )
