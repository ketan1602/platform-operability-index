"""DX measurement: developer experience — error clarity from 3 deliberate mistakes.

Sub-test 2a (error_clarity_a): wrong tool return type (int instead of str).
Sub-test 2b (error_clarity_b): missing required tool argument in the call.
Sub-test 2c (error_clarity_c): wrong LLM client init (bad base_url format).

Scoring per mistake (captured from stderr of the child process):
  3: names problem + location + suggests a fix
  2: names problem and location
  1: names the problem only
  0: generic traceback with no actionable info

P7 overall = p7_from_dx(P7Measurements) in scoring_v2.
TTR score is provided by dx_ttr.sh and stored externally; callers may pass it in via
the `ttr_score` kwarg.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

import structlog

from harness.scenarios.common import env_int, impl_target, workdir
from harness.shared import child
from harness.shared.pillar_models import P7Measurements

log = structlog.get_logger(__name__)

_REPO = Path(__file__).resolve().parents[2]

_FIX_PATTERNS = (
    re.compile(r"should return", re.I),
    re.compile(r"expected.*str", re.I),
    re.compile(r"hint:", re.I),
    re.compile(r"try ", re.I),
    re.compile(r"use ", re.I),
    re.compile(r"change ", re.I),
)
_LOC_PATTERNS = (
    re.compile(r'file ".*"', re.I),
    re.compile(r"line \d+", re.I),
    re.compile(r"at .+:\d+", re.I),
)
_PROBLEM_PATTERNS = (
    re.compile(r"typeerror", re.I),
    re.compile(r"missing.*argument", re.I),
    re.compile(r"invalid.*url", re.I),
    re.compile(r"connection.*refused", re.I),
    re.compile(r"validationerror", re.I),
    re.compile(r"wrong.*type", re.I),
    re.compile(r"return.*type", re.I),
)


def _score_stderr(stderr: str) -> int:
    has_fix = any(p.search(stderr) for p in _FIX_PATTERNS)
    has_loc = any(p.search(stderr) for p in _LOC_PATTERNS)
    has_prob = any(p.search(stderr) for p in _PROBLEM_PATTERNS)
    if has_fix and has_loc and has_prob:
        return 3
    if has_loc and has_prob:
        return 2
    if has_prob:
        return 1
    return 0


def _run_mistake(fw: str, mistake: str) -> int:
    """Spawn the broken child, capture stderr, return clarity score 0-3."""
    path = workdir("DX") / "ledger.jsonl"
    log_path = path.with_suffix(f".dx_{mistake}.log")
    child_env = {"POI_LEDGER": str(path), "PYTHONUNBUFFERED": "1"}
    import os
    env = {**os.environ, **child_env}
    target = impl_target("DX", fw)
    proc = subprocess.Popen(
        [sys.executable, "-m", "harness.shared.child_entry", target,
         f'{{"mistake": "{mistake}"}}'],
        cwd=_REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    timeout = env_int("POI_DX_TIMEOUT_S", 120)
    try:
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate()
    log_path.write_text(stderr)
    score = _score_stderr(stderr)
    log.info("dx.mistake", fw=fw, mistake=mistake, score=score,
             stderr_lines=len(stderr.splitlines()))
    return score


def measure(fw: str, ttr_score: int | None = None) -> dict:
    scores = {m: _run_mistake(fw, m) for m in ("A", "B", "C")}
    m = P7Measurements(
        ttr_score=ttr_score,
        error_clarity_a=scores["A"],
        error_clarity_b=scores["B"],
        error_clarity_c=scores["C"],
    )
    avg_clarity = sum(scores.values()) / 3
    notes = (f"error_clarity A={scores['A']} B={scores['B']} C={scores['C']} "
             f"avg={avg_clarity:.1f} ttr_score={ttr_score}")
    return {"notes": notes, "p7": m}
