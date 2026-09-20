"""CLI — run a single POI pillar test for one framework.

Usage:
  python -m harness.runner --framework F1 --pillar p1 --scenario GEW --impl fixed
  python -m harness.runner --framework F1 --pillar p1 --scenario GEW --impl fixed \\
      --output results/custom.yaml --run-id <uuid>
"""
from __future__ import annotations
import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

from harness.adapters.registry import _auto_discover, get_adapter_dir
from harness.adapters.base import SubprocessRunner

log = structlog.get_logger(__name__)

ADAPTERS_DIR = Path(__file__).parent / "adapters"
RESULTS_DIR = Path(__file__).parent.parent / "results" / "runs"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single POI pillar test")
    parser.add_argument("--framework", required=True, help="Framework ID (F1–F5)")
    parser.add_argument("--pillar", required=True, help="Pillar to run (p1–p5)")
    parser.add_argument("--scenario", required=True, help="Scenario ID (GEW, TCW)")
    parser.add_argument("--impl", required=True, help="Implementation type (fixed, idiomatic)")
    parser.add_argument("--output", default=None, help="Output YAML path (auto-generated if omitted)")
    parser.add_argument("--run-id", default=None, dest="run_id", help="Run UUID (generated if omitted)")
    return parser.parse_args()


def _default_output(framework: str, scenario: str, impl: str, pillar: str, run_id: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{ts}_{framework}_{scenario}_{impl}_{pillar}_{run_id[:8]}.yaml"
    return RESULTS_DIR / name


def main() -> None:
    args = _parse_args()
    run_id = args.run_id or str(uuid.uuid4())

    _auto_discover(ADAPTERS_DIR)
    adapter_dir = get_adapter_dir(args.framework)
    runner = SubprocessRunner.for_adapter(adapter_dir)

    output_path = (
        Path(args.output)
        if args.output
        else _default_output(args.framework, args.scenario, args.impl, args.pillar, run_id)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(
        "runner.start",
        framework=args.framework,
        pillar=args.pillar,
        scenario=args.scenario,
        impl=args.impl,
        run_id=run_id,
        output=str(output_path),
    )

    result = runner.run(args.pillar, args.scenario, args.impl, output_path, run_id=run_id)
    poi_total = result.pillar_scores.poi_total

    log.info("runner.done", output=str(output_path), poi_total=poi_total)
    print(f"Result: {output_path}")
    print(f"POI total: {poi_total}")


if __name__ == "__main__":
    main()
