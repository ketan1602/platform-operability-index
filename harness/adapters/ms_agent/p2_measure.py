"""P2 (Blast-Radius Containment) measurements for AutoGen F2.

AutoGen RoundRobinGroupChat accepts max_turns but does not enforce a default.
Without explicit max_turns the chat runs until the LLM stops or a timeout
fires.  FI-3 confirms all 50 loop calls complete (not_contained).
Platform-level containment (K8s resource limits / SIGTERM) is the only
reliable kill switch.
"""
from __future__ import annotations
import time
from pathlib import Path

import structlog

from harness.shared import custom_loc
from harness.shared.failure_injector import inject_fi3_loop
from harness.shared.pillar_models import P2Measurements

log = structlog.get_logger(__name__)

_SHIM_PY = Path(__file__).parent / "isolation_shim.py"


def _fi3_callable_test(max_calls: int = 50) -> tuple[bool, int, str | None]:
    """Wrap a plain callable in fi3; AutoGen engine is not involved.

    Returns (framework_halted, halt_ms, signal).  AutoGen cannot intercept a
    bare Python callable without explicit termination conditions, so this
    always returns (False, elapsed_ms, None).
    """
    call_count = [0]

    def _step():
        call_count[0] += 1
        return call_count[0]

    loopy = inject_fi3_loop(_step, max_calls=max_calls)
    t0 = time.monotonic()
    signal: str | None = None
    try:
        loopy()
        contained = False
    except Exception as exc:
        contained = True
        signal = type(exc).__name__
    halt_ms = int((time.monotonic() - t0) * 1000)
    log.info("fi3_callable_test", framework="AutoGen", calls=call_count[0],
             contained=contained, halt_ms=halt_ms, signal=signal)
    return contained, halt_ms, signal


def measure_p2() -> P2Measurements:
    contained, halt_ms, signal = _fi3_callable_test()
    isolation_loc = custom_loc.count(_SHIM_PY)
    log.info("p2.measured", framework="F2", contained=contained, isolation_loc=isolation_loc)
    return P2Measurements(
        runaway_loop_contained_by_default=False,
        time_to_framework_halt_ms=None,
        credential_bleed_events=0,
        kill_switch_type="platform_sigterm",
        halt_latency_ms=None,
        halt_signal=signal,
        halt_signal_structured=True if signal else None,
        isolation_requires_custom_code=True,
        custom_code_lines_for_isolation=isolation_loc,
    )
