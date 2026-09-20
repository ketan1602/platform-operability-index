"""Convert raw pillar measurements to 0–3 scores per the POI spec (Section 4).

Each score_pN function is a pure function: given a PNMeasurements object it
returns an integer 0–3.  No side-effects, no I/O.
"""
from __future__ import annotations
from harness.shared.pillar_models import (
    P1Measurements,
    P2Measurements,
    P3Measurements,
    P4Measurements,
    P5Measurements,
)


def score_p1(m: P1Measurements) -> int:
    """P1 — Durable Execution & Replayability."""
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


def score_p2(m: P2Measurements) -> int:
    """P2 — Blast-Radius Containment."""
    bleed = m.credential_bleed_events or 0
    if bleed > 0:
        return 0

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


def score_p3(m: P3Measurements) -> int:
    """P3 — Observability-Nativeness."""
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
    Self-reported time fields (template_creation_time_hrs, deployment_time_hrs)
    are not scored; they may appear in raw data for reference only.
    """
    if not m.one_day_deployment_achieved:
        return 0

    loc = m.template_loc or 0
    if loc > 200:
        return 1

    hacks = m.framework_specific_hacks_required or []
    if not hacks and m.policy_authorable_without_framework_internals:
        return 3

    return 2


def score_p5(m: P5Measurements) -> int:
    """P5 — Day-2 Migration Fragility (inverted: higher = less fragile).

    Scores are derived from two reproducible inputs:
      changelog_breaking_changes_per_release_avg — desk research on changelog
      checkpoint_migration_required              — boolean from changelog

    estimated_fleet_upgrade_hrs_per_release_cycle is intentionally excluded
    from scoring: it is a self-reported estimate that cannot be independently
    reproduced.  The field harness_upgrade_observed_hrs (populated when an
    actual N→N+1 harness upgrade is performed) will replace it in a future
    measurement cycle.
    """
    avg = m.changelog_breaking_changes_per_release_avg
    migr = m.checkpoint_migration_required

    if avg is None:
        return 0

    if avg > 5:
        return 0

    if avg < 1 and not migr:
        return 3

    if avg <= 2 and not migr:
        return 2

    return 1
