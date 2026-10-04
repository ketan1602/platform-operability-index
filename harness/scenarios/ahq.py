"""AHQ measurement: does a paused approval survive a SIGKILL and resume exactly once?

1. Process A runs until the framework's approval gate pauses it, then is SIGKILLed.
2. The approval request travels over RabbitMQ while no agent process exists.
3. After POI_AHQ_PAUSE_S the approval is delivered twice (at-least-once semantics)
   to two fresh processes resuming concurrently.
Evidence: tool ledger (re-executed steps, side-effect count), action fingerprints.
"""
from __future__ import annotations
import importlib
import time
import uuid
from pathlib import Path

from harness.scenarios.common import TrialError, env_int, impl_module, impl_path, workdir
from harness.shared import approval_queue, child, custom_loc, ledger, result_cache
from harness.shared.pillar_models import P1Measurements
from scenarios.ahq.shared import state_store
from scenarios.ahq.shared.tools import EXPECTED_ACTION, digest

_TIMEOUT = "POI_AHQ_TIMEOUT_S"
# Failures of the harness's own plumbing are trial errors, never framework evidence.
_INFRA_ERRORS = {"AMQPConnectionError", "TimeoutError", "OperationalError"}


def _pause(fw: str, run_id: str, wd: str, path) -> tuple[dict, int]:
    proc = child.spawn("harness.scenarios.ahq_trial:start", {"fw": fw, "run_id": run_id, "workdir": wd}, path)
    out = child.watch(proc, path, timeout_s=env_int(_TIMEOUT, 600))
    if out.stop != "held":
        raise TrialError(f"AHQ {fw}: agent never paused for approval ({out.stop}: {out.result})")
    return out.result, proc.pid


def _resume_twice(fw: str, run_id: str, wd: str, path, token) -> list[child.Outcome]:
    start_at = time.time() + env_int("POI_AHQ_BARRIER_S", 15)
    kwargs = {"fw": fw, "run_id": run_id, "workdir": wd, "resume_token": token, "start_at": start_at}
    procs = [child.spawn("harness.scenarios.ahq_trial:resume", kwargs, path) for _ in range(2)]
    return [child.watch(p, path, timeout_s=env_int(_TIMEOUT, 600)) for p in procs]


def _custom_loc(fw: str) -> int:
    loc = custom_loc.count(impl_path("AHQ", fw))
    if importlib.import_module(impl_module("AHQ", fw)).CUSTOM_STORE:
        loc += custom_loc.count(Path(state_store.__file__))
    return loc


def measure(fw: str) -> dict:
    run_id, wd = uuid.uuid4().hex[:12], workdir("AHQ")
    path = wd / "ledger.jsonl"
    paused, pid_a = _pause(fw, run_id, str(wd), path)
    approval_queue.publish_request(run_id, {"pending_digest": paused.get("pending_digest")})
    time.sleep(env_int("POI_AHQ_PAUSE_S", 20))
    approval_queue.publish_decision(run_id, approved=True, copies=2)
    resumes = _resume_twice(fw, run_id, str(wd), path, paused.get("resume_token"))
    infra = [o.result for o in resumes if (o.result or {}).get("signal") in _INFRA_ERRORS]
    if infra:
        raise TrialError(f"AHQ {fw}: resumer could not reach infrastructure: {infra[0]}")
    entries = ledger.read(path)
    resumer_pids = {e["pid"] for e in entries} - {pid_a}
    applies = [e for e in entries if e["event"] == "apply_plan_change"]
    want = digest(EXPECTED_ACTION)
    # Intact: the action that finally ran is the one requested, and matches what A paused on.
    pending_ok = paused.get("pending_digest") in (None, want)
    ok = [o for o in resumes if (o.result or {}).get("stop") == "final_answer"]
    notes = "; ".join(f"resumer {i + 1}: {o.stop}/{(o.result or {}).get('stop')}"
                      + (f" {o.result.get('signal')}" if (o.result or {}).get("signal") else "")
                      for i, o in enumerate(resumes))
    collision = "prevented_by_framework" if len(applies) <= 1 else "not_prevented"
    m = P1Measurements(
        resume_succeeded=bool(ok) and bool(applies),
        state_intact_after_kill=bool(applies) and pending_ok and all(a["digest"] == want for a in applies),
        steps_re_executed_on_resume=max((sum(1 for e in entries if e["event"] == "lookup_account"
                                            and e["pid"] == p) for p in resumer_pids), default=0),
        side_effect_executions=len(applies),
        concurrent_resume_collision=collision,
        resume_latency_ms=min((o.elapsed_ms for o in ok), default=None),
        custom_code_lines_to_reach_score_3=_custom_loc(fw),
        checkpoint_backend=paused.get("backend"),
    )
    result_cache.store(fw, "resume_succeeded", m.resume_succeeded)
    result_cache.store(fw, "concurrent_resume_collision", collision)
    return {"notes": notes, "p1": m}
