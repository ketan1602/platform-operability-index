"""Run POI benchmark combinations, each in its framework's own venv, and write YAML results.

Baseline scenarios (GEW, TCW) run fixed + idiomatic once each in DRY_RUN; in live mode
they also run the measured harnesses (SIGKILL+resume for GEW/P1, fault injection +
Jaeger for TCW/P2P3) repeated POI_REPEATS times. Pure measured scenarios (RLC, SMA,
AHQ, PORT, DX) are idiomatic-only, need live frameworks and ./infra.sh up, and are
repeated POI_REPEATS times (default 5) so scores are medians, not single draws.

Usage:
    DRY_RUN=true python -m harness.run_all --scenarios GEW TCW
    python -m harness.run_all --frameworks F1 F5 --scenarios RLC --repeats 1
"""
from __future__ import annotations
import argparse
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import structlog
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env", override=False)
load_dotenv(_REPO_ROOT / ".env.infra", override=False)

from harness.adapters.base import SubprocessRunner

log = structlog.get_logger(__name__)

_ROOT = Path(__file__).parent.parent
_ADAPTER_DIRS = {"F1": "langgraph", "F2": "ms_agent", "F3": "openai_sdk", "F4": "google_adk", "F5": "strands"}
_FW_NAMES = {"F1": "LangGraph", "F2": "AutoGen", "F3": "OpenAI SDK", "F4": "Google ADK", "F5": "Strands"}
_BASELINE = ("GEW", "TCW")
_MEASURED = ("RLC", "SMA", "AHQ", "GEW", "TCW", "PORT", "DX", "SEC", "OPS")
_IMPLS = ("fixed", "idiomatic")


def _combos(args: argparse.Namespace, dry_run: bool) -> list[tuple[str, str, str, int]]:
    repeats = 1 if dry_run else args.repeats
    out = []
    for fw in args.frameworks:
        for sc in args.scenarios:
            is_baseline = sc in _BASELINE
            is_pure_measured = sc in _MEASURED and not is_baseline
            if is_pure_measured and dry_run:
                continue  # pure-measured scenarios require live infra
            if is_baseline and dry_run:
                # DRY_RUN: run fixed + idiomatic once (no SIGKILL/fault trials)
                out += [(fw, sc, impl, 0) for impl in args.impls]
            elif is_baseline:
                # LIVE: idiomatic only, repeated — adapter triggers measured harness internally
                out += [(fw, sc, "idiomatic", r) for r in range(repeats)]
            else:
                # Pure-measured: idiomatic only, repeated
                out += [(fw, sc, "idiomatic", r) for r in range(repeats)]
    return out


def _already_done(results_dir: Path, fw: str, sc: str, impl: str, rep: int) -> bool:
    """Return True if a successful (error-free) result file already exists."""
    for p in results_dir.glob(f"*_{fw}_{sc}_{impl}_r{rep}_*.yaml"):
        try:
            text = p.read_text()
            if "error: null" in text or "\nerror: ''\n" in text or "\nerror: \"\"\n" in text:
                return True
            # Files written without error field at all (older format) also count.
            if "\nerror:" not in text:
                return True
        except OSError:
            pass
    return False


def _run_one(fw: str, sc: str, impl: str, rep: int, out: Path) -> tuple[bool, str]:
    runner = SubprocessRunner.for_adapter(_ROOT / "harness" / "adapters" / _ADAPTER_DIRS[fw])
    result = runner.run("all", sc, impl, out, run_id=str(uuid.uuid4()), repeat=rep,
                        timeout_s=int(os.environ.get("POI_COMBO_TIMEOUT_S", "3600")))
    return result.error is None, (result.error or "")[:300]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run POI combinations")
    p.add_argument("--results-dir", type=Path, default=_ROOT / "results" / "runs" / "live")
    p.add_argument("--frameworks", nargs="+", choices=list(_ADAPTER_DIRS), default=list(_ADAPTER_DIRS))
    _all_sc = list(dict.fromkeys(_BASELINE + _MEASURED))  # deduplicated, order-preserving
    p.add_argument("--scenarios", nargs="+", choices=_all_sc, default=_all_sc)
    p.add_argument("--impls", nargs="+", choices=_IMPLS, default=list(_IMPLS))
    p.add_argument("--repeats", type=int, default=int(os.environ.get("POI_REPEATS", "5")))
    p.add_argument("--parallel", type=int, default=int(os.environ.get("POI_PARALLEL", "5")))
    p.add_argument("--resume", action="store_true", help="Skip combos whose result file already exists")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    dry_run = os.environ.get("DRY_RUN") == "true"
    args.results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch = uuid.uuid4().hex[:8]
    combos = _combos(args, dry_run)
    if getattr(args, "resume", False):
        skipped = [(fw, sc, impl, rep) for fw, sc, impl, rep in combos
                   if _already_done(args.results_dir, fw, sc, impl, rep)]
        combos = [(fw, sc, impl, rep) for fw, sc, impl, rep in combos
                  if not _already_done(args.results_dir, fw, sc, impl, rep)]
        if skipped:
            print(f"  SKIP {len(skipped)} already-done combos (--resume)", flush=True)
    print(f"Running {len(combos)} combinations → {args.results_dir}", flush=True)
    passed = failed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        futures = {
            pool.submit(_run_one, fw, sc, impl, rep,
                        args.results_dir / f"{ts}_{fw}_{sc}_{impl}_r{rep}_{batch}.yaml"): (fw, sc, impl, rep)
            for fw, sc, impl, rep in combos
        }
        for fut in as_completed(futures):
            fw, sc, impl, rep = futures[fut]
            label = f"{_FW_NAMES[fw]:15s} {sc} {impl} #{rep + 1}"
            try:
                ok, err = fut.result()
            except Exception as exc:
                ok, err = False, str(exc)[:300]
            log.info("combo_finished", fw=fw, sc=sc, impl=impl, repeat=rep, ok=ok)
            print(f"  {'OK  ' if ok else 'FAIL'} {label}" + ("" if ok else f": {err}"), flush=True)
            passed, failed = passed + ok, failed + (not ok)
    print(f"\n{passed} passed  {failed} failed", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
