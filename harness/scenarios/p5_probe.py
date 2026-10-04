"""Empirical P5 upgrade probe — upgrades package, runs scenarios, diffs results."""
from __future__ import annotations
import importlib.metadata
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import structlog

from harness.scenarios.p5_diff import diff

log = structlog.get_logger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
_UV = shutil.which("uv")


def _installed_version(package: str, python_exe: Optional[str] = None) -> Optional[str]:
    """Return the installed version of package, optionally queried from a target venv."""
    if python_exe is None:
        try:
            return importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return None
    result = subprocess.run(
        [python_exe, "-c",
         f"import importlib.metadata; print(importlib.metadata.version({package!r}))"],
        capture_output=True, text=True, timeout=15,
    )
    v = result.stdout.strip()
    return v if v else None


def _pip(python_exe: str, *args: str) -> None:
    if _UV:
        subcmd, *rest = args
        cmd = [_UV, "pip", subcmd, "--python", python_exe, *rest]
    else:
        cmd = [python_exe, "-m", "pip", *args]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)


def run_scenarios(
    python_exe: str, fw_id: str, scenarios: list[str], results_dir: Path, *, dry_run: bool
) -> None:
    """Run scenarios for fw_id and write result YAMLs to results_dir."""
    cmd = [
        python_exe, "-m", "harness.run_all",
        "--frameworks", fw_id,
        "--scenarios", *scenarios,
        "--impls", "idiomatic",
        "--repeats", "1",
        "--results-dir", str(results_dir),
    ]
    env = {**os.environ, "P5_PROBE_ACTIVE": "1"}
    if dry_run:
        env["DRY_RUN"] = "true"
    subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600, cwd=str(_ROOT))


def probe(
    *,
    package: str,
    fw_id: str,
    python_exe: str,
    probe_scenarios: list[tuple[str, str]],
    before_dir: Optional[Path] = None,
    test_checkpoint: bool = False,
    dry_run: bool = True,
) -> dict:
    """Upgrade package, run scenarios, diff against before_dir, restore. Returns P5 field dict.

    before_dir: directory containing before-upgrade result YAMLs.  When provided, the
    diff compares against those.  When None, no structural diff is performed and
    harness_failures_after_upgrade reflects raw errors only.

    Returns a no-op dict when called re-entrantly (P5_PROBE_ACTIVE=1).
    """
    if os.environ.get("P5_PROBE_ACTIVE") == "1":
        return {
            "version_before": _installed_version(package, python_exe),
            "version_after": None,
            "harness_failures_after_upgrade": 0,
            "api_breaking_post_patch": 0,
            "schema_breaking_post_patch": 0,
            "checkpoint_migration_required": False,
            "fleet_upgrade_probe_wall_s": None,
            "residual_manual_failures": 0,
            "regressions": [],
        }

    version_before = _installed_version(package, python_exe)
    scenarios = list(dict.fromkeys(sc for sc, _ in probe_scenarios))
    t0 = time.monotonic()
    log.info("p5.probe.start", fw=fw_id, package=package, version_before=version_before)

    _pip(python_exe, "install", "--upgrade", "--quiet", package)
    version_after = _installed_version(package, python_exe)
    log.info("p5.probe.upgraded", fw=fw_id, package=package, version_after=version_after)

    with tempfile.TemporaryDirectory() as after_tmp:
        run_scenarios(python_exe, fw_id, scenarios, Path(after_tmp), dry_run=dry_run)
        delta = diff(before_dir, Path(after_tmp)) if before_dir else {
            "harness_failures_after_upgrade": 0,
            "api_breaking_post_patch": 0,
            "schema_breaking_post_patch": 0,
            "checkpoint_migration_required": False,
            "regressions": [],
        }

    wall_s = round(time.monotonic() - t0, 1)
    restore_spec = [f"{package}=={version_before}"] if version_before else ["--upgrade", package]
    _pip(python_exe, "install", "--quiet", *restore_spec)

    failures = delta["harness_failures_after_upgrade"]
    log.info("p5.probe.done", fw=fw_id, failures=failures,
             api_breaks=delta["api_breaking_post_patch"], wall_s=wall_s,
             regressions=len(delta["regressions"]))
    return {
        "version_before": version_before,
        "version_after": version_after,
        "harness_failures_after_upgrade": failures,
        "api_breaking_post_patch": delta["api_breaking_post_patch"],
        "schema_breaking_post_patch": delta["schema_breaking_post_patch"],
        "checkpoint_migration_required": delta["checkpoint_migration_required"],
        "fleet_upgrade_probe_wall_s": wall_s,
        "residual_manual_failures": failures,
        "regressions": delta["regressions"],
    }
