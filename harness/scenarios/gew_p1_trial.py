"""Child-side GEW P1 trial: run to the approval checkpoint, or resume from it.

start() runs the workflow until step3_hitl_gate completes and LangGraph interrupts
(interrupt_after=["step3_hitl_gate"]). The parent SIGKILLs the paused child.
resume() rebuilds the same graph with the same Postgres checkpointer (thread_id
is the stable resumption key) and invokes it with None to continue from the saved
checkpoint, executing step4 (CRM update) and step5.
"""
from __future__ import annotations
import os
import time

_FIXED_MODULE = "scenarios.gew.implementations.langgraph.fixed.workflow"


def _require_langgraph(fw: str) -> None:
    if fw != "F1":
        raise RuntimeError(
            f"GEW P1 checkpoint test requires LangGraph (F1); got fw={fw}. "
            "P1 evidence for this framework comes from AHQ only."
        )


def _postgres_checkpointer():
    """Build a Postgres checkpointer — required for SIGKILL+resume durability.

    autocommit=True ensures each checkpoint write is immediately committed so
    a SIGKILL cannot roll it back before the resume process reads it.
    """
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    url = os.environ.get("CHECKPOINT_BACKEND_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError("POSTGRES_URL must be set for GEW P1 Postgres checkpointer")
    conn = psycopg.connect(url, autocommit=True)
    saver = PostgresSaver(conn)
    saver.setup()
    return saver


def start(fw: str, run_id: str, workdir: str, **_) -> dict:
    """Run GEW (LangGraph fixed) until step3 checkpoint; signal hold so parent SIGKILLs."""
    _require_langgraph(fw)
    import importlib
    mod = importlib.import_module(_FIXED_MODULE)
    cp = _postgres_checkpointer()
    graph = mod.build_graph(checkpointer=cp, interrupt_after=["step3_hitl_gate"])
    config: dict = {"configurable": {"thread_id": run_id}}
    graph.invoke({"workflow_id": run_id, "step_log": []}, config)
    return {"hold": True, "thread_id": run_id, "backend": "postgres"}


def resume(fw: str, run_id: str, workdir: str, start_at: float = 0.0, **_) -> dict:
    """Resume GEW from the Postgres checkpoint left by start()."""
    _require_langgraph(fw)
    time.sleep(max(0.0, start_at - time.time()))
    import importlib
    mod = importlib.import_module(_FIXED_MODULE)
    cp = _postgres_checkpointer()
    graph = mod.build_graph(checkpointer=cp)
    config: dict = {"configurable": {"thread_id": run_id}}
    graph.invoke(None, config)
    return {"stop": "final_answer"}
