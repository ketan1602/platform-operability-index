"""P5 (Day-2 Migration Fragility) measurements for OpenAI Agents SDK F3.

Sources: openai-agents PyPI changelog (released March 2025).
Framework is new (< 1 year old) with small stable API surface.
Observed: ~0.5 breaking changes per minor release; no checkpoint schema to migrate.
Fleet estimate: 10 agents × 0.5 h update + 4 h regression = 9 h/cycle.
"""
from __future__ import annotations
import structlog
from harness.shared.pillar_models import P5Measurements

log = structlog.get_logger(__name__)


def measure_p5() -> P5Measurements:
    m = P5Measurements(
        api_breaking_changes_in_patch=0,
        schema_breaking_changes_in_patch=0,
        checkpoint_migration_required=False,
        prompt_rewrites_required=0,
        changelog_breaking_changes_per_release_avg=0.5,
        estimated_fleet_upgrade_hrs_per_release_cycle=9.0,
    )
    log.info(
        "p5.measured",
        framework="F3",
        avg_breaking=m.changelog_breaking_changes_per_release_avg,
        fleet_hrs=m.estimated_fleet_upgrade_hrs_per_release_cycle,
    )
    return m
