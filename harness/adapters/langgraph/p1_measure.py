"""P1 (Durable Execution & Replayability) measurements for LangGraph F1.

Extracted to its own module to keep adapter.py within the 150-line budget.
All optional-dependency imports are deferred inside functions.
Accepts impl_type='fixed'|'idiomatic' to select the workflow implementation.
"""
from __future__ import annotations
import time
import uuid
from pathlib import Path

import structlog

from harness.shared import custom_loc, result_cache
from harness.shared.pillar_models import P1Measurements

log = structlog.get_logger(__name__)

_CHECKPOINT_PY = (
    Path(__file__).parent.parent.parent.parent
    / "scenarios/gew/implementations/langgraph/fixed/checkpoint.py"
)


def _count_checkpoint_loc() -> int:
    """Count only harness-custom lines (between poi:custom markers), not framework API calls."""
    return custom_loc.count(_CHECKPOINT_PY)


def _import_workflow(impl_type: str):
    if impl_type == "idiomatic":
        from scenarios.gew.implementations.langgraph.idiomatic import workflow
    else:
        from scenarios.gew.implementations.langgraph.fixed import workflow
    return workflow


def _t1_baseline(impl_type: str) -> None:
    wf = _import_workflow(impl_type)
    result = wf.run_workflow(workflow_id=str(uuid.uuid4()))
    assert "step5" in (result.get("step_log") or []), "T1: step5 not in step_log"


def _t2_resume(impl_type: str) -> tuple[int, int]:
    from langgraph.checkpoint.memory import MemorySaver
    wf = _import_workflow(impl_type)

    cp = MemorySaver()
    graph = wf.build_graph(checkpointer=cp, interrupt_after=["step2_risk_assessment"])
    tid = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": tid}}
    graph.invoke({"workflow_id": tid, "step_log": []}, cfg)
    pre_log = set((graph.get_state(cfg).values or {}).get("step_log") or [])
    t0 = time.time()
    r2 = graph.invoke(None, cfg)
    resume_ms = int((time.time() - t0) * 1000)
    resume_steps = [s for s in (r2.get("step_log") or []) if s not in pre_log]
    steps_re = sum(1 for s in resume_steps if s in ("step1", "step2"))
    return resume_ms, steps_re


def _t3_idempotency(impl_type: str) -> int:
    """Return actual duplicate CRM tool calls: observed_calls - 1 (expected = exactly 1)."""
    import os
    import tempfile
    from harness.shared import ledger as _ledger
    from scenarios.gew.shared.mock_client import reset_crm_receipts

    wf = _import_workflow(impl_type)
    reset_crm_receipts()
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        tmp = Path(f.name)
    prev = os.environ.get("POI_LEDGER")
    os.environ["POI_LEDGER"] = str(tmp)
    try:
        wf.run_workflow(workflow_id=str(uuid.uuid4()))
    finally:
        if prev is None:
            os.environ.pop("POI_LEDGER", None)
        else:
            os.environ["POI_LEDGER"] = prev
    calls = _ledger.count(_ledger.read(tmp), "gew_crm_updated")
    tmp.unlink(missing_ok=True)
    return max(0, calls - 1)


def _t4_checkpoint_format(impl_type: str) -> str:
    """Probe checkpoint format empirically: run the graph, read back state, try json.dumps.

    MemorySaver state is a Python dict and json-serializable (human_readable).
    When CHECKPOINT_BACKEND_URL is set the production backend is Postgres, which
    stores binary blobs — honest label is "parseable" (structured but not plain text).
    """
    import json
    import os
    from langgraph.checkpoint.memory import MemorySaver

    wf = _import_workflow(impl_type)
    cp = MemorySaver()
    g = wf.build_graph(checkpointer=cp)
    tid = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": tid}}
    g.invoke({"workflow_id": tid, "step_log": []}, cfg)
    try:
        state_values = g.get_state(cfg).values or {}
        json.dumps(state_values)
        return "parseable" if os.environ.get("CHECKPOINT_BACKEND_URL") else "human_readable"
    except (TypeError, ValueError):
        return "opaque"


def measure_p1(impl_type: str = "fixed") -> P1Measurements:
    import os
    ck_loc = _count_checkpoint_loc()
    collision = result_cache.load("F1", "concurrent_resume_collision", "prevented_by_config")
    if os.environ.get("DRY_RUN") == "true":
        log.info("p1.dry_run", impl_type=impl_type)
        return P1Measurements(
            resume_latency_ms=0,
            steps_re_executed_on_resume=0,
            duplicate_tool_calls_on_mid_write=0,
            checkpoint_format="parseable",
            concurrent_resume_collision=collision,
            manual_watchdog_required=False,
            custom_code_lines_to_reach_score_3=ck_loc,
        )
    _t1_baseline(impl_type)
    resume_ms, steps_re = _t2_resume(impl_type)
    dup_calls = _t3_idempotency(impl_type)
    ck_fmt = _t4_checkpoint_format(impl_type)
    log.info(
        "p1.measured",
        impl_type=impl_type,
        resume_ms=resume_ms,
        steps_re_executed=steps_re,
        dup_calls=dup_calls,
        checkpoint_format=ck_fmt,
        checkpoint_loc=ck_loc,
        collision=collision,
    )
    return P1Measurements(
        resume_latency_ms=resume_ms,
        steps_re_executed_on_resume=steps_re,
        duplicate_tool_calls_on_mid_write=dup_calls,
        checkpoint_format=ck_fmt,
        concurrent_resume_collision=collision,
        manual_watchdog_required=False,
        custom_code_lines_to_reach_score_3=ck_loc,
    )
