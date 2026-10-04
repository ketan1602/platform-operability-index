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
from harness.scenarios.dx_extras import _STATIC_P7, run_escape_hatch, run_local
from harness.shared import child, ledger
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


def _elapsed_to_ttr_score(s: float) -> int:
    if s < 5:
        return 3
    if s < 15:
        return 2
    if s < 30:
        return 1
    return 0


def _run_smoke(fw: str) -> tuple[bool, float]:
    """Functional verification: spawn working agent, check tool called, record elapsed."""
    import time
    path = workdir("DX") / "ledger_smoke.jsonl"
    t0 = time.monotonic()
    proc = child.spawn(impl_target("DX", fw), {"mistake": "SMOKE"}, path)
    out = child.watch(proc, path, timeout_s=env_int("POI_DX_TIMEOUT_S", 120))
    elapsed = time.monotonic() - t0
    entries = ledger.read(path)
    verified = (
        out.stop == "exited"
        and (out.result or {}).get("stop") == "final_answer"
        and ledger.count(entries, "dx_smoke") >= 1
    )
    return verified, elapsed


def _run_middleware(fw: str) -> bool:
    """Spawn MIDDLEWARE sub-test child; return True if middleware_fired appears in ledger."""
    path = workdir("DX") / "ledger_middleware.jsonl"
    proc = child.spawn(impl_target("DX", fw), {"mistake": "MIDDLEWARE"}, path)
    child.watch(proc, path, timeout_s=env_int("POI_DX_TIMEOUT_S", 120))
    entries = ledger.read(path)
    fired = ledger.count(entries, "middleware_fired") >= 1
    log.info("dx.middleware", fw=fw, fired=fired)
    return fired


def measure(fw: str, ttr_score: int | None = None) -> dict:
    verified, elapsed_s = _run_smoke(fw)
    ttr = _elapsed_to_ttr_score(elapsed_s) if verified else 0
    scores = {m: _run_mistake(fw, m) for m in ("A", "B", "C", "D", "E")}
    middleware_ok = _run_middleware(fw)
    local_score = run_local(fw)
    escape_score = run_escape_hatch(fw)
    static = _STATIC_P7.get(fw, {})
    m = P7Measurements(
        time_to_first_run_s=round(elapsed_s, 2),
        ttr_score=ttr,
        functional_verified=verified,
        error_clarity_a=scores["A"],
        error_clarity_b=scores["B"],
        error_clarity_c=scores["C"],
        error_clarity_d=scores["D"],
        error_clarity_e=scores["E"],
        middleware_injectable=middleware_ok,
        local_testability_score=local_score,
        escape_hatch_score=escape_score,
        community_score=static.get("community_score"),
        vendor_independence_score=static.get("vendor_independence_score"),
    )
    avg_clarity = sum(scores.values()) / len(scores)
    notes = (
        f"smoke={'ok' if verified else 'FAIL'} ttr={ttr} ({elapsed_s:.1f}s); "
        f"error_clarity A={scores['A']} B={scores['B']} C={scores['C']} "
        f"D={scores['D']} E={scores['E']} avg={avg_clarity:.1f}; "
        f"middleware={middleware_ok} local={local_score} escape={escape_score}; "
        f"community={static.get('community_score')} "
        f"vendor_ind={static.get('vendor_independence_score')}"
    )
    return {"notes": notes, "p7": m}
