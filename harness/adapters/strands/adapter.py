"""Strands Agents adapter — F5.

Pillar methods for the baseline scenarios (GEW, TCW). Routing, the measured
scenarios (RLC, SMA, AHQ) and scoring live in BaseAdapter.
"""
from __future__ import annotations

import structlog

from harness.adapters.shared.base_adapter import BaseAdapter
from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements, P4Measurements, P5Measurements

log = structlog.get_logger()
# Estimated LOC for a minimal custom state-serialisation wrapper that
# achieves score-3 checkpoint/resume behaviour absent from Strands natively.
_CUSTOM_STATE_LOC = 80


class StrandsAdapter(BaseAdapter):
    framework_id = "F5"
    package = "strands-agents"

    def _run_p1(self, scenario_id: str, impl_type: str) -> P1Measurements:
        if scenario_id.upper() == "TCW":
            from harness.adapters.shared.tcw_p1 import validate_tcw_t1
            validate_tcw_t1("F5", impl_type)
        if impl_type == "idiomatic":
            from scenarios.gew.implementations.strands_agents.idiomatic.workflow import run_workflow
        else:
            from scenarios.gew.implementations.strands_agents.fixed.workflow import run_workflow

        result = run_workflow(workflow_id="p1-baseline")
        all_steps = result.get("step_log", [])
        completed = len(all_steps) == 5

        log.info("p1_baseline_run", impl_type=impl_type, completed=completed, steps=all_steps)

        assert completed, f"Expected 5 steps, got {all_steps}"

        return P1Measurements(
            # T2: no native checkpoint/resume — manual wrapper required
            manual_watchdog_required=True,
            checkpoint_format="opaque",
            resume_latency_ms=None,
            # T3: idempotency key applied at CRM tool level → 0 duplicate calls
            duplicate_tool_calls_on_mid_write=0,
            # T5: framework provides no concurrent-resume guard
            concurrent_resume_collision="not_prevented",
            steps_re_executed_on_resume=None,
            # LOC estimate for a custom state-serialisation wrapper
            custom_code_lines_to_reach_score_3=_CUSTOM_STATE_LOC,
        )

    def _run_p2(self, scenario_id: str, impl_type: str) -> P2Measurements:
        from harness.adapters.strands.p2_measure import measure_p2
        return measure_p2()

    def _run_p3(self, scenario_id: str, impl_type: str) -> P3Measurements:
        from harness.adapters.strands.p3_measure import measure_p3
        return measure_p3(run_id=f"p3-{scenario_id}-{impl_type}")

    def _run_p4(self, scenario_id: str, impl_type: str) -> P4Measurements:
        from harness.adapters.strands.p4_measure import measure_p4
        return measure_p4()

    def _run_p5(self, scenario_id: str, impl_type: str) -> P5Measurements:
        from harness.adapters.strands.p5_measure import measure_p5
        return measure_p5()
