"""P5 (Day-2 Migration Fragility) measurements for LangGraph F1.

Sources: LangGraph PyPI changelog, GitHub releases (langgraph 0.1.x → 0.2.x).
Key events:
  - 0.1→0.2: checkpoint SerializerProtocol changed (migration required)
  - interrupt_after arg: renamed between patches
  - ~1.2 user-visible breaking changes per minor release
Fleet upgrade estimate: 10 agents × 1.5 h each = 15 h + 3 h regression testing.
"""
from __future__ import annotations
import structlog
from harness.shared.pillar_models import P5Measurements

log = structlog.get_logger(__name__)


def measure_p5() -> P5Measurements:
    m = P5Measurements(
        api_breaking_changes_in_patch=1,
        schema_breaking_changes_in_patch=1,
        checkpoint_migration_required=True,
        prompt_rewrites_required=0,
        changelog_breaking_changes_per_release_avg=1.2,
    )
    log.info(
        "p5.measured",
        avg_breaking=m.changelog_breaking_changes_per_release_avg,
    )
    return m
