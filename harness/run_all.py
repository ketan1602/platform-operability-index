"""Run every POI benchmark combination in-process and write YAML results.

Covers all 5 frameworks × 2 scenarios × 2 impl types × all 5 pillars.
Requires DRY_RUN=true unless real LLM / infra credentials are configured.

Usage:
    DRY_RUN=true python -m harness.run_all
    DRY_RUN=true python -m harness.run_all --results-dir /tmp/poi-results
"""
from __future__ import annotations
import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

_ROOT = Path(__file__).parent.parent

_ADAPTERS = {
    "F1": ("harness.adapters.langgraph.adapter", "LangGraphAdapter"),
    "F2": ("harness.adapters.ms_agent.adapter",  "AutoGenAdapter"),
    "F3": ("harness.adapters.openai_sdk.adapter", "OpenAISDKAdapter"),
    "F4": ("harness.adapters.google_adk.adapter", "GoogleADKAdapter"),
    "F5": ("harness.adapters.strands.adapter",    "StrandsAdapter"),
}
_FRAMEWORKS = list(_ADAPTERS)
_SCENARIOS  = ["GEW", "TCW"]
_IMPLS      = ["fixed", "idiomatic"]

_FW_NAMES = {
    "F1": "LangGraph",
    "F2": "AutoGen",
    "F3": "OpenAI SDK",
    "F4": "Google ADK",
    "F5": "Strands",
}


def _build_meta(fw: str, sc: str, impl: str, version: str):
    from harness.shared.measurement import (
        FrameworkId, ScenarioId, ImplementationType, Pillar, RunMetadata,
    )
    return RunMetadata(
        framework_id=FrameworkId(fw),
        framework_version=version,
        scenario_id=ScenarioId(sc),
        implementation_type=ImplementationType(impl),
        pillar=Pillar.ALL,
    )


def _load_adapter(fw: str):
    mod_path, cls_name = _ADAPTERS[fw]
    mod = __import__(mod_path, fromlist=[cls_name])
    return getattr(mod, cls_name)()


def _run_combo(fw: str, sc: str, impl: str) -> str:
    adapter = _load_adapter(fw)
    meta = _build_meta(fw, sc, impl, adapter.framework_version)
    result = adapter.run(meta, "all", sc, impl)
    return result.to_yaml()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run all POI combinations")
    p.add_argument("--results-dir", type=Path,
                   default=_ROOT / "results" / "runs")
    p.add_argument("--frameworks", nargs="+", choices=_FRAMEWORKS, default=_FRAMEWORKS)
    p.add_argument("--scenarios",  nargs="+", choices=_SCENARIOS,  default=_SCENARIOS)
    p.add_argument("--impls",      nargs="+", choices=_IMPLS,      default=_IMPLS)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    results_dir: Path = args.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)

    if os.environ.get("DRY_RUN") != "true":
        log.warning("dry_run_not_set", msg="Set DRY_RUN=true to avoid real LLM calls")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_batch = str(uuid.uuid4())[:8]
    passed = failed = 0

    combos = [
        (fw, sc, impl)
        for fw in args.frameworks
        for sc in args.scenarios
        for impl in args.impls
    ]

    print(f"Running {len(combos)} combinations → {results_dir}", flush=True)
    for fw, sc, impl in combos:
        label = f"{_FW_NAMES[fw]:15s} {sc} {impl}"
        out = results_dir / f"{ts}_{fw}_{sc}_{impl}_{run_batch}.yaml"
        try:
            yaml_text = _run_combo(fw, sc, impl)
            out.write_text(yaml_text)
            print(f"  OK   {label}", flush=True)
            passed += 1
        except Exception as exc:
            log.error("combo_failed", fw=fw, sc=sc, impl=impl, error=str(exc))
            print(f"  FAIL {label}: {exc}", flush=True)
            failed += 1

    print(f"\n{passed} passed  {failed} failed", flush=True)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
