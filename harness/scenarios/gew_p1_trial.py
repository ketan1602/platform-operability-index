"""Child-side GEW P1 trial: run to the approval checkpoint, or resume from it.

start() runs the workflow until step3_hitl_gate completes and LangGraph interrupts
(interrupt_after=["step3_hitl_gate"]). The parent SIGKILLs the paused child.
resume() rebuilds the same graph with the same Postgres checkpointer (thread_id
is the stable resumption key) and invokes it with None to continue from the saved
checkpoint, executing step4 (CRM update) and step5.
"""
from __future__ import annotations
import importlib
import time

from harness.scenarios.common import impl_module


def start(fw: str, run_id: str, workdir: str, **_) -> dict:
    """Run GEW until step3 checkpoint; signal hold so parent SIGKILLs."""
    mod = importlib.import_module(impl_module("GEW", fw))
    graph = mod.build_graph(interrupt_after=["step3_hitl_gate"])
    config: dict = {"configurable": {"thread_id": run_id}}
    graph.invoke({"workflow_id": run_id, "step_log": []}, config)
    return {"hold": True, "thread_id": run_id, "backend": "postgres"}


def resume(fw: str, run_id: str, workdir: str, start_at: float = 0.0, **_) -> dict:
    """Resume GEW from the Postgres checkpoint left by start()."""
    time.sleep(max(0.0, start_at - time.time()))
    mod = importlib.import_module(impl_module("GEW", fw))
    graph = mod.build_graph()
    config: dict = {"configurable": {"thread_id": run_id}}
    graph.invoke(None, config)
    return {"stop": "final_answer"}
