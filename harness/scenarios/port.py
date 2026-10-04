"""PORT measurement: P6 Switching Cost.

Tests whether the framework can invoke plain Python functions (no framework
imports, no framework decorators) as tools without modification. Counts how many
of the three canonical tools the LLM actually called.

The isolation sub_test lives in each framework's workflow.py and is exercised
by sma.py Trial C (concurrent in-process multi-tenancy check), not here.
"""
from __future__ import annotations

import structlog

from harness.scenarios import port_cross, port_diff
from harness.scenarios.common import env_int, impl_target, workdir
from harness.shared import child, ledger
from harness.shared.pillar_models import P6Measurements
from scenarios.port.shared.tools import TOOL_ANALYSE, TOOL_DRAFT, TOOL_SEARCH

log = structlog.get_logger(__name__)


def _port_metrics_for(fw: str, metrics: dict) -> tuple:
    fw_data = metrics.get(fw)
    if fw_data:
        return fw_data["avg_reuse_rate"], fw_data["avg_changed_lines"]
    return None, None


def measure(fw: str) -> dict:
    # --- tools_raw sub-test: plain functions, no framework decorator ---
    raw_path = workdir("PORT") / "ledger_raw.jsonl"
    raw_proc = child.spawn(impl_target("PORT", fw), {"sub_test": "tools_raw"}, raw_path)
    raw_out = child.watch(raw_proc, raw_path, timeout_s=env_int("POI_PORT_TIMEOUT_S", 300))
    raw_entries = ledger.read(raw_path)
    called = sum(
        1 for t in [TOOL_SEARCH, TOOL_ANALYSE, TOOL_DRAFT]
        if ledger.count(raw_entries, t) >= 1
    )

    # --- switch sub-test: framework-wrapped tools, task completion ---
    path = workdir("PORT") / "ledger_switch.jsonl"
    proc = child.spawn(impl_target("PORT", fw), {"sub_test": "switch"}, path)
    out = child.watch(proc, path, timeout_s=env_int("POI_PORT_TIMEOUT_S", 300))
    task_ok = out.stop == "exited" and (out.result or {}).get("stop") == "final_answer"
    state_json_safe = (out.result or {}).get("state_json_safe")

    # --- context_port sub-test: conversation history portability ---
    ctx_path = workdir("PORT") / "ledger_ctx.jsonl"
    ctx_proc = child.spawn(impl_target("PORT", fw), {"sub_test": "context_port"}, ctx_path)
    ctx_out = child.watch(ctx_proc, ctx_path, timeout_s=env_int("POI_PORT_TIMEOUT_S", 300))
    ctx_result = (ctx_out.result or {})
    context_portable = ctx_result.get("context_portable")
    context_injection = ctx_result.get("injection")

    metrics = port_diff.port_metrics()
    reuse_rate, changed_lines = _port_metrics_for(fw, metrics)
    cross_venv_rate = port_cross.measure_cross_venv(fw)
    m = P6Measurements(
        tools_called_unmodified=called,
        task_completed=task_ok,
        state_json_safe=state_json_safe,
        port_reuse_rate=reuse_rate,
        port_changed_lines=changed_lines,
        context_portable=context_portable,
        context_injection=context_injection,
        cross_venv_success_rate=cross_venv_rate,
    )
    notes = (
        f"tools_called={called}/3 task_completed={task_ok} "
        f"context_portable={context_portable} injection={context_injection}"
    )
    if reuse_rate is not None:
        notes += f" port_reuse={reuse_rate:.0%} changed={changed_lines}"
    if cross_venv_rate is not None:
        notes += f" cross_venv={cross_venv_rate:.0%}"
    log.info("port.measure", fw=fw, tools_called=called,
             context_portable=context_portable, injection=context_injection,
             cross_venv_rate=cross_venv_rate)
    return {"notes": notes, "p6": m}
