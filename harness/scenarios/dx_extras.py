"""Additional P7 sub-tests: local testability (LOCAL), escape hatch, and HITL gate."""
from __future__ import annotations
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from harness.scenarios.common import env_int, impl_target, workdir
from harness.shared import child, custom_loc, ledger

_REPO = Path(__file__).resolve().parents[2]

_STATIC_P7: dict[str, dict[str, int]] = {
    "F1": {"community_score": 3, "vendor_independence_score": 3},
    "F2": {"community_score": 2, "vendor_independence_score": 3},
    "F3": {"community_score": 2, "vendor_independence_score": 1},
    "F4": {"community_score": 2, "vendor_independence_score": 2},
    "F5": {"community_score": 1, "vendor_independence_score": 2},
}

_FW_WORKFLOW: dict[str, str] = {
    "F1": "scenarios/dx/implementations/langgraph/idiomatic/workflow.py",
    "F2": "scenarios/dx/implementations/ms_agent/idiomatic/workflow.py",
    "F3": "scenarios/dx/implementations/openai_agents_sdk/idiomatic/workflow.py",
    "F4": "scenarios/dx/implementations/google_adk/idiomatic/workflow.py",
    "F5": "scenarios/dx/implementations/strands_agents/idiomatic/workflow.py",
}

_AUTH_PATTERNS = (
    re.compile(r"api.?key", re.I), re.compile(r"unauthorized", re.I),
    re.compile(r"authentication", re.I), re.compile(r"credential", re.I),
    re.compile(r"\b401\b"),
)
_FIX_PATTERNS = (
    re.compile(r"hint:", re.I), re.compile(r"try ", re.I),
    re.compile(r"use ", re.I), re.compile(r"change ", re.I),
)
_LOC_PATTERNS = (
    re.compile(r'file ".*"', re.I), re.compile(r"line \d+", re.I),
    re.compile(r"at .+:\d+", re.I),
)

_CRED_KEYS = frozenset({
    "AIREFINERY_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY",
})


def _score_local_stderr(stderr: str) -> int:
    """Score: how clearly does the framework report missing API credentials?"""
    has_auth = any(p.search(stderr) for p in _AUTH_PATTERNS)
    has_loc = any(p.search(stderr) for p in _LOC_PATTERNS)
    has_hint = any(p.search(stderr) for p in _FIX_PATTERNS)
    if has_hint and has_auth:
        return 3
    if has_auth and has_loc:
        return 2
    if has_auth:
        return 1
    return 0


def run_local(fw: str) -> int:
    """Run DX SMOKE without API credentials; score clarity of the resulting error (0-3)."""
    path = workdir("DX") / "ledger_local.jsonl"
    log_path = path.with_suffix(".dx_local.log")
    env = {k: v for k, v in os.environ.items() if k not in _CRED_KEYS}
    env["POI_LEDGER"] = str(path)
    env["PYTHONUNBUFFERED"] = "1"
    target = impl_target("DX", fw)
    proc = subprocess.Popen(
        [sys.executable, "-m", "harness.shared.child_entry", target, '{"mistake": "SMOKE"}'],
        cwd=_REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    timeout = env_int("POI_DX_TIMEOUT_S", 120)
    try:
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate()
    log_path.write_text(stderr)
    return _score_local_stderr(stderr)


def run_escape_hatch(fw: str) -> int:
    """Spawn ESCAPE_HATCH dispatch; return probes_passed (0-3)."""
    path = workdir("DX") / "ledger_escape.jsonl"
    proc = child.spawn(impl_target("DX", fw), {"mistake": "ESCAPE_HATCH"}, path)
    out = child.watch(proc, path, timeout_s=env_int("POI_DX_TIMEOUT_S", 120))
    return int((out.result or {}).get("probes_passed", 0))


def count_hitl_loc(fw: str) -> int:
    """Count operator LOC inside _mistake_hitl via poi:custom-begin/end markers."""
    rel = _FW_WORKFLOW.get(fw, "")
    path = _REPO / rel if rel else None
    if not path or not path.exists():
        return 0
    return custom_loc.count(path)


def run_hitl(fw: str) -> tuple[bool, int]:
    """Spawn HITL child, approve via file, verify hitl_completed. Returns (works, gate_latency_ms)."""
    import tempfile
    approval = Path(tempfile.mktemp(suffix=".hitl_approval"))
    path = workdir("DX") / "ledger_hitl.jsonl"
    env = {**os.environ, "POI_HITL_APPROVAL": str(approval),
           "POI_LEDGER": str(path), "PYTHONUNBUFFERED": "1"}
    target = impl_target("DX", fw)
    proc = subprocess.Popen(
        [sys.executable, "-m", "harness.shared.child_entry", target, '{"mistake": "HITL"}'],
        cwd=_REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    t_approved: list[float] = []

    def _approve():
        deadline = time.time() + env_int("POI_DX_TIMEOUT_S", 120)
        while time.time() < deadline:
            if path.exists() and ledger.count(ledger.read(path), "hitl_hold") >= 1:
                t_approved.append(time.monotonic())
                approval.write_text("approved")
                return
            time.sleep(0.3)

    t = threading.Thread(target=_approve, daemon=True)
    t.start()
    try:
        proc.communicate(timeout=env_int("POI_DX_TIMEOUT_S", 120))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
    t_done = time.monotonic()
    t.join(timeout=5)
    works = path.exists() and ledger.count(ledger.read(path), "hitl_completed") >= 1
    gate_ms = int((t_done - t_approved[0]) * 1000) if t_approved else -1
    return works, gate_ms
