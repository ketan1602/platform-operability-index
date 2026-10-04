"""Convert raw pillar measurements to 0–3 scores per the POI spec (Section 4).

Each score_pN function is a pure function: given a PNMeasurements object it
returns an integer 0–3.  No side-effects, no I/O.
"""
from __future__ import annotations
from typing import Optional

from harness.shared import scoring_v2, scoring_ops
from harness.shared.pillar_models import (
    P1Measurements,
    P2Measurements,
    P3Measurements,
    P4Measurements,
    P5Measurements,
    P6Measurements,
    P7Measurements,
    P8Measurements,
    P9Measurements,
)


def score_p1(m: P1Measurements) -> int:
    """P1 — Durable Execution & Replayability."""
    if m.resume_succeeded is not None:
        return scoring_v2.p1_from_resume(m)
    re_exec = m.steps_re_executed_on_resume or 0
    dups = m.duplicate_tool_calls_on_mid_write or 0
    fmt = m.checkpoint_format or ""

    if re_exec > 0 or fmt == "opaque":
        return 0

    if (
        not m.manual_watchdog_required
        and dups == 0
        and m.concurrent_resume_collision == "prevented_by_framework"
        and fmt == "human_readable"
    ):
        return 3

    if dups == 0 and fmt == "parseable":
        return 2

    return 1


def score_p2(m: P2Measurements) -> Optional[float]:
    """P2 — Blast-Radius Containment."""
    bleed = m.credential_bleed_events or 0
    if bleed > 0:
        return 0
    if m.failure_propagation is not None:
        return scoring_v2.p2_from_isolation(m)
    if m.loop_halted_by_framework is not None:
        return scoring_v2.p2_from_loop(m)

    if m.isolation_requires_custom_code:
        return 1

    halt = m.halt_latency_ms
    if halt is not None and halt < 5000:
        if (
            m.runaway_loop_contained_by_default
            and m.kill_switch_type == "framework_native"
        ):
            return 3
        return 2

    return 1


def score_p3(m: P3Measurements) -> float:
    """P3 — Observability-Nativeness."""
    if m.framework_spans is not None:
        return scoring_v2.p3_from_traces(m)
    if not m.oss_stack_viable:
        return 0

    if m.proprietary_backend_required or m.custom_exporter_required:
        return 1

    if not m.missing_required_attributes and m.alert_fired_without_custom_code:
        return 3

    return 2


def score_p4(m: P4Measurements) -> int:
    """P4 — Golden-Path Packageability.

    Scoring inputs are all observable from the repo:
      template_loc      — counted by _count_template_loc() in each p4_measure.py
      framework_specific_hacks_required — documented list in each p4_measure.py
      policy_authorable_without_framework_internals — boolean desk-check
    K8s fit sub-tests:
      sigterm_graceful=False caps score at 1.
      lazy_init_s > 5.0 caps score at 2.
    Self-reported time fields are not scored; they appear in raw data for reference only.
    """
    if not m.one_day_deployment_achieved:
        return 0

    if m.sigterm_graceful is False:
        return 1

    loc = m.template_loc or 0
    if loc > 200:
        return 1

    hacks = m.framework_specific_hacks_required or []
    hack_cost = sum(h.cost_hrs for h in hacks)
    if not hacks and m.policy_authorable_without_framework_internals:
        raw = 3
    elif hack_cost <= 4.0:
        raw = 2
    else:
        raw = 1

    if (m.lazy_init_s is not None) and (m.lazy_init_s < 0 or m.lazy_init_s > 5.0):
        return min(raw, 2)

    if m.hitl_verified is False:
        return min(raw, 1)

    if m.hitl_native is True and m.hitl_verified is True:
        raw = min(raw + 1, 3)
    elif m.hitl_gate_loc is not None and m.hitl_native is False and m.hitl_gate_loc > 15:
        raw = min(raw, 2)

    return raw


def score_p6(m: P6Measurements) -> int:
    """P6 — Portability (12-Factor + SOLID compliance, behavioural)."""
    return scoring_v2.p6_from_portability(m)


def score_p7(m: P7Measurements) -> int:
    """P7 — Developer Experience (timed + error clarity)."""
    return scoring_v2.p7_from_dx(m)


def score_p8(m: P8Measurements) -> int:
    """P8 — Security Posture (behavioural sub-tests)."""
    return scoring_v2.p8_from_security(m)


def score_p9(m: P9Measurements) -> int:
    """P9 — Ops Experience (FinOps + Runtime + Fleet management)."""
    return scoring_ops.p9_from_ops(m)


def score_p5(m: P5Measurements) -> int:
    """P5 — Day-2 Migration Fragility (higher = less fragile).
    Empirically probed: upgrade package in venv, re-run DRY_RUN scenarios, diff results.
    """
    if m.harness_failures_after_upgrade == 0 and not m.checkpoint_migration_required:
        return 3
    if m.checkpoint_migration_required or m.harness_failures_after_upgrade >= 3:
        return 1
    return 2
