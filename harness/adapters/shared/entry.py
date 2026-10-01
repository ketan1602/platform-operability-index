"""Shared subprocess entry point for every framework adapter.

Runs inside the adapter's own venv; each adapter's run.py is a shim calling main().
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import structlog

from harness.shared.measurement import (FrameworkId, ImplementationType, Pillar, RunMetadata,
                                        RunResult, ScenarioId)

log = structlog.get_logger()


def _parse_args(name: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=f"{name} adapter subprocess entry point")
    p.add_argument("--pillar", required=True, choices=[x.value for x in Pillar])
    p.add_argument("--scenario", required=True, choices=[x.value for x in ScenarioId])
    p.add_argument("--impl", required=True, choices=[x.value for x in ImplementationType])
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--run-id", default=None)
    p.add_argument("--repeat", type=int, default=0)
    return p.parse_args()


def _meta(args: argparse.Namespace, adapter) -> RunMetadata:
    extra = {"run_id": args.run_id} if args.run_id else {}
    return RunMetadata(
        framework_id=FrameworkId(adapter.framework_id), framework_version=adapter.framework_version,
        scenario_id=ScenarioId(args.scenario), implementation_type=ImplementationType(args.impl),
        pillar=Pillar(args.pillar), repeat=args.repeat, **extra,
    )


def main(adapter_cls) -> None:
    adapter = adapter_cls()
    args = _parse_args(adapter_cls.__name__)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    meta = _meta(args, adapter)
    try:
        result = adapter.run(meta, args.pillar, args.scenario, args.impl)
    except Exception as exc:
        log.error("adapter_run_failed", framework=adapter.framework_id, scenario=args.scenario,
                  error=str(exc), exc_info=True)
        args.output.write_text(RunResult(run_metadata=meta, error=str(exc)[:2000]).to_yaml())
        sys.exit(1)
    args.output.write_text(result.to_yaml())
    log.info("adapter_run_complete", output=str(args.output))
