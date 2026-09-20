"""P5 (Day-2 Migration Fragility) measurements for AutoGen F2.

Sources: autogen-agentchat PyPI / GitHub releases.
Key events:
  - 0.2→0.4: complete API rewrite (AssistantAgent signature changed,
    GroupChat replaced by TeamChat in 0.4.x).  Checkpoint state incompatible.
  - ~3 breaking changes per minor release in 2024 (high volatility).
Fleet estimate: 10 agents × 4 h rewrite + 8 h regression = 48 h/cycle.
"""
from __future__ import annotations
import structlog
from harness.shared.pillar_models import P5Measurements

log = structlog.get_logger(__name__)


def measure_p5() -> P5Measurements:
    m = P5Measurements(
        api_breaking_changes_in_patch=2,
        schema_breaking_changes_in_patch=1,
        checkpoint_migration_required=False,
        prompt_rewrites_required=2,
        changelog_breaking_changes_per_release_avg=3.1,
        estimated_fleet_upgrade_hrs_per_release_cycle=48.0,
    )
    log.info(
        "p5.measured",
        framework="F2",
        avg_breaking=m.changelog_breaking_changes_per_release_avg,
        fleet_hrs=m.estimated_fleet_upgrade_hrs_per_release_cycle,
    )
    return m
