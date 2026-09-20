"""P5 (Day-2 Migration Fragility) measurements for Google ADK F4.

Sources: google-adk PyPI changelog (released 2025, v0.x series).
Google has a history of deprecating Cloud AI APIs; ADK is in pre-GA.
Observed: ~1.5 breaking changes per minor release; session API changed in 0.3.
Fleet estimate: 10 agents × 2 h update + 5 h regression = 25 h/cycle.
"""
from __future__ import annotations
import structlog
from harness.shared.pillar_models import P5Measurements

log = structlog.get_logger(__name__)


def measure_p5() -> P5Measurements:
    m = P5Measurements(
        api_breaking_changes_in_patch=1,
        schema_breaking_changes_in_patch=1,
        checkpoint_migration_required=False,
        prompt_rewrites_required=1,
        changelog_breaking_changes_per_release_avg=1.5,
    )
    log.info(
        "p5.measured",
        framework="F4",
        avg_breaking=m.changelog_breaking_changes_per_release_avg,
    )
    return m
