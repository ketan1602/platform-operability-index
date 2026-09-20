"""CLI — run all 5 POI pillars for one framework and write a summary YAML.

Usage:
  python -m harness.full_run --framework F1 --scenario GEW --impl fixed
  python -m harness.full_run --framework F1 --scenario GEW --impl fixed --run-id <uuid>
"""
from __future__ import annotations
import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
import yaml

from harness.adapters.registry import _auto_discover, get_adapter_dir
from harness.adapters.base import SubprocessRunner

log = structlog.get_logger(__name__)

ADAPTERS_DIR = Path(__file__).parent / "adapters"
RESULTS_DIR = Path(__file__).parent.parent / "results" / "runs"
PILLARS = ["p1", "p2", "p3", "p4", "p5"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all 5 POI pillars for one framework")
    parser.add_argument("--framework", required=True, help="Framework ID (F1–F5)")
    parser.add_argument("--scenario", required=True, help="Scenario ID (GEW, TCW)")
    parser.add_argument("--impl", required=True, help="Implementation type (fixed, idiomatic)")
    parser.add_argument("--run-id", default=None, dest="run_id", help="Run UUID (generated if omitted)")
    return parser.parse_args()


def _write_summary(
    run_dir: Path,
    run_id: str,
    framework: str,
    scenario: str,
    impl: str,
    scores: dict[str, Optional[int]],
) -> Path:
    poi_total = sum(v for v in scores.values() if v is not None)
    summary = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "framework": framework,
        "scenario": scenario,
        "impl": impl,
        "pillar_scores": scores,
        "poi_total": poi_total,
    }
    path = run_dir / "summary.yaml"
    path.write_text(yaml.dump(summary, default_flow_style=False, sort_keys=False))
    log.info("summary.written", path=str(path), poi_total=poi_total)
    return path


def _run_pillars(
    runner: SubprocessRunner,
    run_dir: Path,
    scenario: str,
    impl: str,
    run_id: str,
) -> dict[str, Optional[int]]:
    scores: dict[str, Optional[int]] = {}
    for pillar in PILLARS:
        output_path = run_dir / f"{pillar}.yaml"
        log.info("full_run.pillar_start", pillar=pillar)
        try:
            result = runner.run(pillar, scenario, impl, output_path, run_id=run_id)
            score = getattr(result.pillar_scores, pillar, None)
            scores[pillar] = score
            log.info("full_run.pillar_done", pillar=pillar, score=score)
        except Exception as exc:
            log.error("full_run.pillar_error", pillar=pillar, error=str(exc))
            scores[pillar] = None
    return scores


def main() -> None:
    args = _parse_args()
    run_id = args.run_id or str(uuid.uuid4())
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RESULTS_DIR / f"{ts}_{args.framework}_{args.scenario}_{args.impl}_{run_id[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)

    _auto_discover(ADAPTERS_DIR)
    adapter_dir = get_adapter_dir(args.framework)
    runner = SubprocessRunner.for_adapter(adapter_dir)

    log.info(
        "full_run.start",
        framework=args.framework,
        scenario=args.scenario,
        impl=args.impl,
        run_id=run_id,
        run_dir=str(run_dir),
    )

    scores = _run_pillars(runner, run_dir, args.scenario, args.impl, run_id)
    summary_path = _write_summary(
        run_dir, run_id, args.framework, args.scenario, args.impl, scores
    )

    log.info("full_run.complete", summary=str(summary_path))
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
