"""P5 version matrix: pin each framework to older versions, probe upgrade to latest.

Usage:
    python -m harness.scenarios.p5_version_matrix [--frameworks F1 F2 ...]

Each framework is downgraded to each test version, then the empirical probe runs
(upgrade to latest + DRY_RUN harness + restore).  Results are printed as a table.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Any

import structlog

import tempfile

from harness.scenarios.p5_probe import _installed_version, _pip, probe, run_scenarios
from harness.shared.scoring import score_p5
from harness.shared.pillar_models import P5Measurements

log = structlog.get_logger(__name__)

_ROOT = Path(__file__).resolve().parents[2]

# fmt: off
_ADAPTERS: dict[str, dict[str, Any]] = {
    "F1": {
        "package": "langgraph",
        "venv": "harness/adapters/langgraph/.venv/bin/python3",
        "scenarios": [("TCW", "idiomatic"), ("SMA", "idiomatic")],
        "test_checkpoint": True,
        # current 1.2.12 — 2 minors back + 1 major back
        "versions": {"minor_1": "1.1.10", "minor_2": "1.0.10", "major": "0.6.11"},
    },
    "F2": {
        "package": "autogen-agentchat",
        "venv": "harness/adapters/ms_agent/.venv/bin/python3",
        "scenarios": [("TCW", "idiomatic"), ("SMA", "idiomatic")],
        "test_checkpoint": False,
        # current 0.7.5 — 2 minors back (0.5.x is a major API rewrite)
        "versions": {"minor_1": "0.6.4", "minor_2": "0.5.7", "major": "0.4.9.3"},
    },
    "F3": {
        "package": "openai-agents",
        "venv": "harness/adapters/openai_sdk/.venv/bin/python3",
        "scenarios": [("TCW", "idiomatic"), ("SMA", "idiomatic")],
        "test_checkpoint": False,
        # current 0.22.3 — 3 minors back + far-back (no true major version yet)
        "versions": {"minor_1": "0.20.0", "minor_2": "0.17.8", "major": "0.10.5"},
    },
    "F4": {
        "package": "google-adk",
        "venv": "harness/adapters/google_adk/.venv/bin/python3",
        "scenarios": [("TCW", "idiomatic"), ("SMA", "idiomatic")],
        "test_checkpoint": False,
        # current 2.10.0 — 3 minors back + 1 major back
        "versions": {"minor_1": "2.8.0", "minor_2": "2.7.1", "major": "1.39.1"},
    },
    "F5": {
        "package": "strands-agents",
        "venv": "harness/adapters/strands/.venv/bin/python3",
        "scenarios": [("TCW", "idiomatic"), ("SMA", "idiomatic")],
        "test_checkpoint": False,
        # current 1.57.1 — 3 minors back + 1 major back (0.x)
        "versions": {"minor_1": "1.55.1", "minor_2": "1.54.0", "major": "0.3.0"},
    },
}
# fmt: on

_FW_LABELS = {
    "F1": "LangGraph",
    "F2": "AutoGen",
    "F3": "OpenAI SDK",
    "F4": "Google ADK",
    "F5": "Strands",
}


def _downgrade(python_exe: str, package: str, target: str) -> None:
    log.info("version_matrix.downgrade", package=package, target=target)
    _pip(python_exe, "install", "--quiet", f"{package}=={target}")


def _probe_from_version(fw_id: str, cfg: dict, test_version: str, *, dry_run: bool = True) -> dict:
    python_exe = str(_ROOT / cfg["venv"])
    package = cfg["package"]
    scenarios = list(dict.fromkeys(sc for sc, _ in cfg["scenarios"]))

    original_version = _installed_version(package, python_exe)
    _downgrade(python_exe, package, test_version)
    pinned_version = _installed_version(package, python_exe)

    # Capture before-state at the pinned version, then probe upgrade.
    with tempfile.TemporaryDirectory() as before_tmp:
        run_scenarios(python_exe, fw_id, scenarios, Path(before_tmp), dry_run=dry_run)
        result = probe(
            package=package,
            fw_id=fw_id,
            python_exe=python_exe,
            probe_scenarios=cfg["scenarios"],
            before_dir=Path(before_tmp),
            test_checkpoint=cfg["test_checkpoint"],
            dry_run=dry_run,
        )

    # Probe restores to test_version; restore to original before returning.
    if original_version and original_version != pinned_version:
        _pip(python_exe, "install", "--quiet", f"{package}=={original_version}")

    result["pinned_version"] = pinned_version
    return result


def run_matrix(fw_ids: list[str], *, dry_run: bool = True) -> list[dict]:
    rows: list[dict] = []
    for fw_id in fw_ids:
        cfg = _ADAPTERS[fw_id]
        for label, version in cfg["versions"].items():
            log.info("version_matrix.start", fw=fw_id, label=label, version=version)
            try:
                result = _probe_from_version(fw_id, cfg, version, dry_run=dry_run)
                m = P5Measurements(**{k: v for k, v in result.items() if k != "pinned_version"})
                rows.append({
                    "fw": fw_id,
                    "label": label,
                    "pinned": result.get("pinned_version") or version,
                    "latest": result.get("version_after") or "?",
                    "failures": result["harness_failures_after_upgrade"],
                    "api_breaks": result["api_breaking_post_patch"],
                    "schema_breaks": result["schema_breaking_post_patch"],
                    "wall_s": result.get("fleet_upgrade_probe_wall_s"),
                    "score": score_p5(m),
                })
            except Exception as exc:
                log.error("version_matrix.error", fw=fw_id, version=version, err=str(exc))
                rows.append({"fw": fw_id, "label": label, "pinned": version, "error": str(exc)})
    return rows


def _print_table(rows: list[dict]) -> None:
    header = f"{'FW':<12} {'Label':<9} {'From':>8} {'To':>8} {'Fail':>5} {'API':>4} {'Schema':>7} {'Wall(s)':>8} {'P5':>3}"
    print()
    print(header)
    print("-" * len(header))
    for r in rows:
        if "error" in r:
            print(f"{_FW_LABELS.get(r['fw'], r['fw']):<12} {r['label']:<9} {r['pinned']:>8}  ERROR: {r['error'][:40]}")
            continue
        fw_label = _FW_LABELS.get(r["fw"], r["fw"])
        wall = f"{r['wall_s']:.1f}" if r.get("wall_s") is not None else "-"
        print(
            f"{fw_label:<12} {r['label']:<9} {r['pinned']:>8} {r['latest']:>8}"
            f" {r['failures']:>5} {r['api_breaks']:>4} {r['schema_breaks']:>7}"
            f" {wall:>8} {r['score']:>3}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="P5 version-matrix upgrade probe")
    parser.add_argument("--frameworks", nargs="*", default=list(_ADAPTERS), metavar="FW")
    parser.add_argument("--no-dry-run", action="store_true", help="Run real LLM scenarios instead of DRY_RUN")
    args = parser.parse_args()
    fw_ids = [f.upper() for f in args.frameworks]
    unknown = [f for f in fw_ids if f not in _ADAPTERS]
    if unknown:
        sys.exit(f"Unknown frameworks: {unknown}. Valid: {list(_ADAPTERS)}")
    rows = run_matrix(fw_ids, dry_run=not args.no_dry_run)
    _print_table(rows)


if __name__ == "__main__":
    main()
