"""Subprocess entry point for the Google ADK adapter.

Runs inside the adapter's own venv. Imports from harness.shared via sys.path
manipulation so the package need not be installed in the adapter venv.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import structlog  # noqa: E402  (after sys.path setup)

from harness.shared.measurement import (  # noqa: E402
    FrameworkId,
    ImplementationType,
    Pillar,
    RunMetadata,
    RunResult,
    ScenarioId,
)
from harness.adapters.google_adk.adapter import GoogleADKAdapter  # noqa: E402

log = structlog.get_logger()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Google ADK adapter subprocess entry point")
    p.add_argument("--pillar", required=True, choices=["p1", "p2", "p3", "p4", "p5", "all"])
    p.add_argument("--scenario", required=True, choices=["GEW", "TCW"])
    p.add_argument("--impl", required=True, choices=["fixed", "idiomatic"])
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--run-id", default=None)
    return p.parse_args()


def _build_meta(args: argparse.Namespace, adapter: GoogleADKAdapter) -> RunMetadata:
    extra = {"run_id": args.run_id} if args.run_id else {}
    return RunMetadata(
        framework_id=FrameworkId.F4,
        framework_version=adapter.framework_version,
        scenario_id=ScenarioId(args.scenario),
        implementation_type=ImplementationType(args.impl),
        pillar=Pillar(args.pillar),
        **extra,
    )


def _write_error(args: argparse.Namespace, message: str) -> None:
    extra = {"run_id": args.run_id} if args.run_id else {}
    meta = RunMetadata(
        framework_id=FrameworkId.F4,
        framework_version="unknown",
        scenario_id=ScenarioId(args.scenario),
        implementation_type=ImplementationType(args.impl),
        pillar=Pillar(args.pillar),
        **extra,
    )
    result = RunResult(run_metadata=meta, error=message)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.to_yaml())


def main() -> None:
    args = _parse_args()
    adapter = GoogleADKAdapter()

    try:
        meta = _build_meta(args, adapter)
        result = adapter.run(meta, args.pillar, args.scenario, args.impl)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.to_yaml())
        log.info("adapter_run_complete", output=str(args.output))
    except Exception as exc:
        log.error("adapter_run_failed", error=str(exc), exc_info=True)
        _write_error(args, str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
