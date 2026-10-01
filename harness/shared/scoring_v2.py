"""Scoring rules for measured evidence from the RLC, SMA and AHQ scenarios.

None means inconclusive: the scenario ran but produced no evidence for the pillar
(e.g. the model stopped calling the tool before any limit could be tested).
"""
from __future__ import annotations
from typing import Optional

from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements, P8Measurements, P6Measurements, P7Measurements

_PROPAGATION_SCORE = {"contained": 3, "crashed_run": 1, "hung": 0}


def p1_from_resume(m: P1Measurements) -> int:
    """AHQ: 0 cannot resume · 1 resumes lossy · 2 clean but custom/unsafe · 3 native, safe."""
    if not m.resume_succeeded:
        return 0
    if not m.state_intact_after_kill or (m.steps_re_executed_on_resume or 0) > 0:
        return 1
    if m.custom_code_lines_to_reach_score_3 > 0 or (m.side_effect_executions or 0) > 1:
        return 2
    return 3


def p2_from_loop(m: P2Measurements) -> Optional[int]:
    """RLC: 3 default halt with typed signal · 2 halts only untyped or when configured · 1 platform kill."""
    if m.model_self_terminated:  # default behaviour never exercised: no evidence either way
        return None
    if m.loop_halted_by_framework:
        return 3 if m.halt_signal_structured else 2
    if m.configured_limit_honored:
        return 2
    return 1


def p2_from_isolation(m: P2Measurements) -> float:
    """SMA: continuous score from sibling completion ratio (0–3).

    Max siblings = total specialists - 1 failing = 2 (SMA uses 3 specialists).
    sibling_agents_completed / 2 * 3 → 0.0 | 1.5 | 3.0
    Falls back to propagation enum when sibling count is absent.
    """
    siblings = m.sibling_agents_completed
    if siblings is not None:
        return round(min(siblings / 2.0, 1.0) * 3.0, 1)
    return float(_PROPAGATION_SCORE.get(m.failure_propagation or "", 0))


def p3_from_traces(m: P3Measurements) -> float:
    """SMA/TCW: continuous score (0.0–3.0) from spans + attribute coverage + trace connectivity.

    base 1.0  — framework emits any gen_ai spans
    +0–1.0    — attribute coverage: (present / total_required)
    +0–1.0    — connectivity: (agents_traced / agents_invoked) × orphan penalty
    """
    if not m.framework_spans:
        return 0.0
    present = len(m.required_attributes_emitted_by_default or [])
    missing = len(m.missing_required_attributes or [])
    total = present + missing
    attr_score = present / total if total > 0 else 1.0
    invoked = m.agents_invoked or 1
    traced = m.agents_traced or 0
    connectivity = traced / invoked
    if m.orphan_spans:
        connectivity *= 0.5
    if m.custom_exporter_loc and m.custom_exporter_loc > 0:
        connectivity *= 0.75
    return min(round(1.0 + attr_score + connectivity, 1), 3.0)


def p6_from_portability(m: P6Measurements) -> int:
    """PORT: count passed sub-tests; map 0→0, 1-2→1, 3→2, 4→3."""
    passed = sum(1 for v in [m.config_portability, m.process_isolation,
                              m.tool_extensibility, m.backend_portability] if v is True)
    if passed == 4:
        return 3
    if passed == 3:
        return 2
    if passed >= 1:
        return 1
    return 0


def p7_from_dx(m: P7Measurements) -> int:
    """DX: weighted average of TTR score and error clarity average, mapped to 0-3."""
    ttr = m.ttr_score if m.ttr_score is not None else 0
    clarity_vals = [v for v in [m.error_clarity_a, m.error_clarity_b, m.error_clarity_c] if v is not None]
    clarity_avg = sum(clarity_vals) / len(clarity_vals) if clarity_vals else 0
    raw = (ttr + clarity_avg) / 2
    if raw >= 2.5:
        return 3
    if raw >= 1.5:
        return 2
    if raw >= 0.5:
        return 1
    return 0


def p8_from_security(m: P8Measurements) -> int:
    """SEC: sum of 3 behavioural sub-tests (0-3). Each None sub-test counts as 0."""
    injection = int(bool(m.prompt_injection_resisted))
    boundary = int(bool(m.tool_boundary_enforced))
    secret = int(not bool(m.secret_leaked_in_telemetry))
    return injection + boundary + secret
