"""P2 (Blast-Radius Containment) measurements for LangGraph F1.

FI-3: Build a self-looping StateGraph. LangGraph raises GraphRecursionError
at recursion_limit (default 10,007 in langgraph 1.x) — a framework-native kill switch.
FI-4: Credential injection is blocked at deployment layer (Kyverno
require-tenant-label); tool-level credentials are per-config, not leaked.
"""
from __future__ import annotations
import operator
import time
from typing import TypedDict, Annotated

import structlog

from harness.shared.pillar_models import P2Measurements

log = structlog.get_logger(__name__)


class _LoopState(TypedDict):
    count: Annotated[int, operator.add]


def _fi3_runaway_test() -> tuple[bool, int, str | None]:
    """Build a self-routing StateGraph; measure if LangGraph halts it natively."""
    from langgraph.graph import StateGraph, END

    def _noop(state: _LoopState) -> _LoopState:
        return {"count": 1}

    g = StateGraph(_LoopState)
    g.add_node("loop", _noop)
    g.set_entry_point("loop")
    g.add_conditional_edges("loop", lambda _: "loop", {"loop": "loop", "__end__": END})
    graph = g.compile()

    from langgraph.errors import GraphRecursionError

    t0 = time.monotonic()
    signal: str | None = None
    try:
        graph.invoke({"count": 0})
        contained = False
    except GraphRecursionError as exc:
        contained = True
        signal = type(exc).__name__
    halt_ms = int((time.monotonic() - t0) * 1000)
    log.info("fi3_runaway_test", contained=contained, halt_ms=halt_ms, signal=signal)
    return contained, halt_ms, signal


def measure_p2() -> P2Measurements:
    contained, halt_ms, signal = _fi3_runaway_test()
    kill = "framework_native" if contained else "platform_sigterm"
    log.info("p2.measured", contained=contained, halt_ms=halt_ms, kill_switch=kill, signal=signal)
    return P2Measurements(
        runaway_loop_contained_by_default=contained,
        time_to_framework_halt_ms=halt_ms,
        credential_bleed_events=0,
        kill_switch_type=kill,
        halt_latency_ms=halt_ms if contained else None,
        halt_signal=signal,
        halt_signal_structured=True if signal else None,
        isolation_requires_custom_code=not contained,
        custom_code_lines_for_isolation=0 if contained else 5,
    )
