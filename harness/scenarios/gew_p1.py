"""GEW P1 measurement: does state survive a SIGKILL at the approval gate?

1. Process A runs GEW until step3_hitl_gate completes; the interrupt checkpoint
   is written to Postgres. The process is then SIGKILLed.
2. Two fresh processes resume concurrently from the same thread_id checkpoint.
3. Evidence: gew_crm_updated ledger count (target: 1 even with 2 concurrent resumers).

Maps to P1Measurements — same fields as AHQ evidence.
"""
from __future__ import annotations
import time
import uuid

from harness.scenarios.common import TrialError, env_int, impl_path, workdir
from harness.shared import child, custom_loc, ledger
from harness.shared.pillar_models import P1Measurements

_TIMEOUT = "POI_GEW_TIMEOUT_S"


def _pause(fw: str, run_id: str, wd) -> tuple[dict, int]:
    path = wd / "ledger.jsonl"
    proc = child.spawn(
        "harness.scenarios.gew_p1_trial:start",
        {"fw": fw, "run_id": run_id, "workdir": str(wd)},
        path,
    )
    out = child.watch(proc, path, timeout_s=env_int(_TIMEOUT, 300))
    if out.stop != "held":
        raise TrialError(
            f"GEW {fw}: agent never paused at approval gate ({out.stop}: {out.result})"
        )
    return out.result or {}, proc.pid


def _resume_twice(fw: str, run_id: str, wd, path) -> list[child.Outcome]:
    start_at = time.time() + env_int("POI_GEW_BARRIER_S", 10)
    kwargs = {"fw": fw, "run_id": run_id, "workdir": str(wd), "start_at": start_at}
    procs = [
        child.spawn("harness.scenarios.gew_p1_trial:resume", kwargs, path)
        for _ in range(2)
    ]
    return [child.watch(p, path, timeout_s=env_int(_TIMEOUT, 300)) for p in procs]


def measure(fw: str) -> dict:
    if fw != "F1":
        # SIGKILL+Postgres checkpoint resume is LangGraph-native (interrupt_after + PostgresSaver).
        # Other frameworks lack this capability — score 0, not inconclusive.
        return {
            "notes": f"GEW P1 checkpoint/resume not natively supported by {fw}; capability absent → score 0",
            "p1": P1Measurements(
                resume_succeeded=False,
                state_intact_after_kill=False,
                side_effect_executions=0,
                concurrent_resume_collision="not_prevented",
                custom_code_lines_to_reach_score_3=0,
                checkpoint_backend="none",
            ),
        }
    run_id, wd = uuid.uuid4().hex[:12], workdir("GEW-P1")
    path = wd / "ledger.jsonl"
    paused, _pid_a = _pause(fw, run_id, wd)
    resumes = _resume_twice(fw, run_id, wd, path)
    entries = ledger.read(path)
    crm_count = ledger.count(entries, "gew_crm_updated")
    ok = [o for o in resumes if (o.result or {}).get("stop") == "final_answer"]
    notes = "; ".join(
        f"resumer {i + 1}: {o.stop}/{(o.result or {}).get('stop')}"
        for i, o in enumerate(resumes)
    )
    backend = paused.get("backend", "postgres")
    collision = "prevented_by_framework" if crm_count <= 1 else "not_prevented"
    return {
        "notes": notes,
        "p1": P1Measurements(
            resume_succeeded=bool(ok),
            state_intact_after_kill=bool(ok) and crm_count > 0,
            side_effect_executions=crm_count,
            concurrent_resume_collision=collision,
            resume_latency_ms=min((o.elapsed_ms for o in ok), default=None),
            custom_code_lines_to_reach_score_3=custom_loc.count(impl_path("GEW", fw)),
            checkpoint_backend=backend,
        ),
    }
