"""PORT measurement: 12-Factor / SOLID portability across 4 behavioural sub-tests.

Sub-test 1 (config_portability):  static — model config comes from env vars, not code.
Sub-test 2 (process_isolation):   3 concurrent child processes share no ledger state.
Sub-test 3 (tool_extensibility):  dynamically added tool called successfully.
Sub-test 4 (backend_portability): no hardcoded connection strings in the implementation.
"""
from __future__ import annotations
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import structlog

from harness.scenarios.common import TrialError, env_int, impl_path, impl_target, workdir
from harness.shared import child, ledger
from harness.shared.pillar_models import P6Measurements
from scenarios.port.shared.tools import TOOL_EVENT_FETCH, TOOL_EVENT_WEATHER

log = structlog.get_logger(__name__)

_HARDCODED_MODELS = ("gpt-4", "gpt-3.5", "claude-", "gemini-", "llama-")
_HARDCODED_URLS = ("postgres://", "postgresql://", "sqlite://", "localhost:5432")


def _check_config_portability(fw: str) -> bool:
    """Sub-test 1: implementation must not hardcode a model name."""
    path = impl_path("PORT", fw)
    if not path.exists():
        return False
    src = path.read_text()
    return not any(tok in src for tok in _HARDCODED_MODELS)


def _check_backend_portability(fw: str) -> bool:
    """Sub-test 4: implementation must not hardcode a connection string."""
    path = impl_path("PORT", fw)
    if not path.exists():
        return False
    src = path.read_text()
    return not any(tok in src for tok in _HARDCODED_URLS)


def _isolation_trial(fw: str, run_id: str) -> tuple[bool, str]:
    """Run one isolation child; return (success, run_id)."""
    path = workdir("PORT") / "ledger.jsonl"
    proc = child.spawn(impl_target("PORT", fw), {"sub_test": "isolation", "run_id": run_id}, path)
    out = child.watch(proc, path, timeout_s=env_int("POI_PORT_TIMEOUT_S", 300))
    if out.stop != "exited" or not out.result:
        return False, run_id
    result_run_id = (out.result or {}).get("run_id", "")
    entries = ledger.read(path)
    contaminated = any(e.get("run_id") not in (run_id, None) for e in entries
                       if e.get("event") == TOOL_EVENT_FETCH)
    return not contaminated and result_run_id == run_id, run_id


def _check_process_isolation(fw: str) -> bool:
    """Sub-test 2: 3 concurrent children each write only their own run_id."""
    run_ids = [str(uuid.uuid4()) for _ in range(3)]
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_isolation_trial, fw, rid): rid for rid in run_ids}
        for fut in as_completed(futures):
            ok, rid = fut.result()
            results.append(ok)
            log.info("port.isolation_trial", fw=fw, run_id=rid, ok=ok)
    return all(results)


def _check_tool_extensibility(fw: str) -> bool:
    """Sub-test 3: agent calls get_weather without modifying the agent class."""
    path = workdir("PORT") / "ledger.jsonl"
    proc = child.spawn(impl_target("PORT", fw), {"sub_test": "tool_ext"}, path)
    out = child.watch(proc, path, timeout_s=env_int("POI_PORT_TIMEOUT_S", 300))
    if out.stop != "exited" or (out.result or {}).get("stop") != "final_answer":
        return False
    entries = ledger.read(path)
    return ledger.count(entries, TOOL_EVENT_WEATHER) >= 1


def measure(fw: str) -> dict:
    cfg = _check_config_portability(fw)
    back = _check_backend_portability(fw)
    iso = _check_process_isolation(fw)
    tool_ext = _check_tool_extensibility(fw)
    log.info("port.measure", fw=fw, config=cfg, backend=back, isolation=iso, tool_ext=tool_ext)
    m = P6Measurements(
        config_portability=cfg,
        process_isolation=iso,
        tool_extensibility=tool_ext,
        backend_portability=back,
    )
    passed = sum(1 for v in [cfg, iso, tool_ext, back] if v)
    notes = (f"config={cfg} isolation={iso} tool_ext={tool_ext} backend={back} "
             f"({passed}/4 sub-tests passed)")
    return {"notes": notes, "p6": m}
