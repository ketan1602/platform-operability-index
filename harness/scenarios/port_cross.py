"""Empirical cross-framework porting test: run ported SMA workflows; measure success rate.

For each framework F under test, the SMA scenario already ships ported-from-<other>
workflow implementations (one per source framework). This module runs each ported
workflow through F's own venv and measures what fraction complete successfully.

High success rate  → F is a good porting TARGET (low switching cost to reach it).
Low success rate   → the port introduced runtime failures (higher switching cost).

Timeout per workflow controlled by POI_PORT_CROSS_TIMEOUT_S (default 180s).
"""
from __future__ import annotations
from pathlib import Path

from harness.scenarios.common import IMPL_DIRS, env_int, workdir
from harness.shared import child

_ROOT = Path(__file__).resolve().parents[2]

_PORT_DIR = {
    "F1": "ported_from_langgraph",
    "F2": "ported_from_autogen",
    "F3": "ported_from_openai_sdk",
    "F4": "ported_from_google_adk",
    "F5": "ported_from_strands",
}
_TIMEOUT = "POI_PORT_CROSS_TIMEOUT_S"


def _target(fw: str, src_fw: str) -> str:
    return (
        f"scenarios.sma.implementations.{IMPL_DIRS[fw]}"
        f".{_PORT_DIR[src_fw]}.workflow:run"
    )


def _workflow_exists(fw: str, src_fw: str) -> bool:
    path = _ROOT / (_target(fw, src_fw).split(":")[0].replace(".", "/") + ".py")
    return path.exists()


def _run_ported(fw: str, src_fw: str, wd: Path) -> bool | None:
    """Return True=success, False=runtime failure, None=ported workflow not found."""
    if not _workflow_exists(fw, src_fw):
        return None
    ledger_path = wd / f"cross_{src_fw}.jsonl"
    proc = child.spawn(_target(fw, src_fw), {}, ledger_path)
    out = child.watch(proc, ledger_path, timeout_s=env_int(_TIMEOUT, 180))
    return out.stop == "exited" and out.result is not None


def measure_cross_venv(fw: str) -> float | None:
    """Run all ported-from-* SMA workflows for fw; return fraction that succeed.

    Returns None if no ported workflows are found (portability matrix not yet populated).
    """
    wd = workdir("PORT-CROSS")
    sources = [f for f in _PORT_DIR if f != fw]
    outcomes = [_run_ported(fw, src, wd) for src in sources]
    valid = [o for o in outcomes if o is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 3)
