"""Spawn and supervise one trial process: the harness acts as the platform.

The supervisor can SIGKILL a child when it exceeds a tool-call ceiling (a runaway
the framework did not stop), a wall-clock timeout, or once it reports it is holding
(waiting on a human). SIGKILL, not SIGTERM: a graceful shutdown would let the
framework flush state and flatter its durability score.
"""
from __future__ import annotations
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from harness.shared import ledger
from harness.shared.child_entry import RESULT_PREFIX

_REPO = Path(__file__).resolve().parents[2]

# Tracks all grandchild ledger paths registered during one measure() call so
# base_adapter can aggregate token counts across all trials.
_ledger_registry: list[Path] = []


def reset_ledger_registry() -> None:
    _ledger_registry.clear()


def collect_tokens() -> dict:
    """Sum llm_usage entries across every ledger registered since the last reset."""
    all_entries: list = []
    for path in _ledger_registry:
        all_entries.extend(ledger.read(path))
    return ledger.sum_tokens(all_entries)


@dataclass
class Outcome:
    stop: str                 # exited | ceiling | timeout | held
    result: Optional[dict]    # the child's POI_RESULT payload, if it printed one
    elapsed_ms: int


def spawn(target: str, kwargs: dict, ledger_path: Path, env: Optional[dict] = None) -> subprocess.Popen:
    _ledger_registry.append(ledger_path)
    child_env = {**os.environ, **(env or {}), ledger.LEDGER_ENV: str(ledger_path), "PYTHONUNBUFFERED": "1"}
    log_file = open(ledger_path.with_suffix(f".{target.split(':')[1]}.{time.time_ns()}.log"), "w")
    return subprocess.Popen(
        [sys.executable, "-m", "harness.shared.child_entry", target, json.dumps(kwargs)],
        cwd=_REPO, env=child_env, stdout=subprocess.PIPE, stderr=log_file, text=True,
    )


def _reader(proc: subprocess.Popen, out: queue.Queue) -> None:
    for line in proc.stdout:
        if line.startswith(RESULT_PREFIX):
            out.put(json.loads(line[len(RESULT_PREFIX):]))
    out.put(None)


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait()


def watch(
    proc: subprocess.Popen,
    ledger_path: Path,
    timeout_s: float,
    ceiling: Optional[tuple[str, int]] = None,
) -> Outcome:
    """Supervise until the child exits, holds, hits the ceiling, or times out."""
    results: queue.Queue = queue.Queue()
    threading.Thread(target=_reader, args=(proc, results), daemon=True).start()
    t0 = time.monotonic()
    while True:
        elapsed = int((time.monotonic() - t0) * 1000)
        try:
            item = results.get(timeout=0.2)
        except queue.Empty:
            item = "pending"
        if isinstance(item, dict):
            if item.get("hold"):
                _kill(proc)
                return Outcome("held", item, elapsed)
            proc.wait()
            return Outcome("exited", item, elapsed)
        if item is None:
            return Outcome("exited", None, elapsed)
        if ceiling and ledger.count(ledger.read(ledger_path), ceiling[0]) >= ceiling[1]:
            _kill(proc)
            return Outcome("ceiling", None, elapsed)
        if elapsed > timeout_s * 1000:
            _kill(proc)
            return Outcome("timeout", None, elapsed)
