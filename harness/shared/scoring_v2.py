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
    """RLC: 3 default halt with typed signal · 2 halts only untyped or when configured · 1 platform kill.
    Inconclusive only when Trial 1 self-terminated AND Trial 2 produced no signal."""
    if m.model_self_terminated and m.configured_limit_honored is None:
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
    Multi-tenancy failure (concurrent_tenancy_safe=False) caps score at 1.5.
    """
    siblings = m.sibling_agents_completed
    if siblings is not None:
        result = round(min(siblings / 2.0, 1.0) * 3.0, 1)
    else:
        result = float(_PROPAGATION_SCORE.get(m.failure_propagation or "", 0))
    if m.concurrent_tenancy_safe is False:
        return min(result, 1.5)
    return result


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
    """P6 — Switching Cost & Portability: three equal-weight portability dimensions.

    Sub-score 1 — Tool portability (weight 40%):
        tools_called_unmodified / 3  → 0.0–1.0
        Plain Python tools work unchanged across frameworks.

    Sub-score 2 — Context portability (weight 40%):
        native  + True  → 1.0   framework API natively loads standard history
        fallback + True → 0.5   works but developer must write a serialiser
        any     + False → 0.0   cannot resume from neutral conversation history

    Sub-score 3 — Switching cost / LOC (weight 20%):
        port_changed_lines ≤ 25 → 1.0   low rewrite burden when porting away
        port_changed_lines > 25 → 0.0   high entanglement, more lines to rewrite

    Final = round((sub1×0.4 + sub2×0.4 + sub3×0.2) × 3), clipped to [0, 3].
    """
    tool_sub = min(m.tools_called_unmodified, 3) / 3.0

    if m.context_portable is True and m.context_injection == "native":
        ctx_sub = 1.0
    elif m.context_portable is True:
        ctx_sub = 0.5
    else:
        ctx_sub = 0.0

    if m.cross_venv_success_rate is not None:
        sw_sub = m.cross_venv_success_rate
    else:
        changed = m.port_changed_lines
        sw_sub = 1.0 if (changed is not None and changed <= 25) else 0.0

    weighted = tool_sub * 0.4 + ctx_sub * 0.4 + sw_sub * 0.2
    return min(round(weighted * 3), 3)


def p7_from_dx(m: P7Measurements) -> int:
    """DX: 4-cluster weighted score (0-3).

    Ergonomics    (40%): TTR + error-clarity average (Mistakes A-E)
    Dev Quality   (20%): middleware injectable + local testability
    Ecosystem     (20%): community support score (static research-backed)
    Vendor Ind.   (20%): vendor independence + escape hatch capability

    Returns 0 if functional_verified is False.
    Caps at 2 if middleware_injectable is False.
    """
    if m.functional_verified is False:
        return 0

    ttr = m.ttr_score if m.ttr_score is not None else 0
    clarity_vals = [v for v in [
        m.error_clarity_a, m.error_clarity_b, m.error_clarity_c,
        m.error_clarity_d, m.error_clarity_e,
    ] if v is not None]
    clarity_avg = sum(clarity_vals) / len(clarity_vals) if clarity_vals else 0
    ergonomics = (ttr + clarity_avg) / 2  # 0-3

    mw = 3.0 if m.middleware_injectable else 0.0
    local = float(m.local_testability_score or 0)
    dev_quality = (mw + local) / 2  # 0-3

    ecosystem = float(m.community_score or 0)  # 0-3

    vi = float(m.vendor_independence_score or 0)
    esc = float(m.escape_hatch_score or 0)
    vendor_ind = (vi + esc) / 2  # 0-3

    weighted = ergonomics * 0.40 + dev_quality * 0.20 + ecosystem * 0.20 + vendor_ind * 0.20
    score = min(round(weighted), 3)

    if m.middleware_injectable is False:
        return min(score, 2)
    return score


def p8_from_security(m: P8Measurements) -> int:
    """SEC: 6 sub-tests across two layers, weighted to a 0-3 score.

    Framework layer (60% weight — A/B/C):
        tool_scope_enforced, context_isolation_verified, telemetry_clean
    K8s layer (40% weight — D/E):
        k8s_scope_enforced, admission_blocked

    HTTP bleed modifier: if the framework leaks POI_BLEED_TOKEN to an external
    HTTP endpoint (http_cred_bleed_events > 0), the score is capped at 2.

    Final = round(raw * 3), capped at 3.
    None is treated as 0 (sub-test not yet run).
    """
    fw_score = (
        int(bool(m.tool_scope_enforced))
        + int(bool(m.context_isolation_verified))
        + int(bool(m.telemetry_clean))
    ) / 3.0 * 0.6
    k8s_score = (
        int(bool(m.k8s_scope_enforced))
        + int(bool(m.admission_blocked))
    ) / 2.0 * 0.4
    base = min(round((fw_score + k8s_score) * 3), 3)
    if m.http_cred_bleed_events is not None and m.http_cred_bleed_events > 0:
        return min(base, 2)
    return base
