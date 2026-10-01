"""AutoGen / MS AgentChat adapter — F2.

Pillar methods for the baseline scenarios (GEW, TCW). Routing, the measured
scenarios (RLC, SMA, AHQ) and scoring live in BaseAdapter.
"""
from __future__ import annotations
import uuid

import structlog

from harness.adapters.shared.base_adapter import BaseAdapter
from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements, P4Measurements, P5Measurements

log = structlog.get_logger()
_EXPECTED_STEPS = {
    "step1_fetch_data",
    "step2_score_risk",
    "step3_hitl_gate",
    "step4_crm_write",
    "step5_audit",
}


class AutoGenAdapter(BaseAdapter):
    framework_id = "F2"
    package = "autogen-agentchat"

    def _run_p1(self, scenario_id: str, impl_type: str) -> P1Measurements:
        import uuid
        if scenario_id.upper() == "TCW":
            from harness.adapters.shared.tcw_p1 import validate_tcw_t1
            validate_tcw_t1("F2", impl_type)
        if impl_type == "idiomatic":
            from scenarios.gew.implementations.ms_agent.idiomatic.workflow import run_workflow
        else:
            from scenarios.gew.implementations.ms_agent.fixed.workflow import run_workflow

        workflow_id = f"p1-t1-{uuid.uuid4().hex[:8]}"
        result = run_workflow(workflow_id)
        step_log: set = set(result.get("step_log", []))
        missing = _EXPECTED_STEPS - step_log
        if missing:
            raise RuntimeError(f"P1-T1 ({impl_type}): workflow missing steps: {missing}")

        log.info("p1_t1_baseline_complete", workflow_id=workflow_id,
                 impl_type=impl_type, steps=list(step_log))

        return P1Measurements(
            resume_latency_ms=None,
            steps_re_executed_on_resume=None,
            duplicate_tool_calls_on_mid_write=0,
            checkpoint_format="opaque",
            concurrent_resume_collision="not_prevented",
            manual_watchdog_required=True,
            custom_code_lines_to_reach_score_3=0,
        )

    def _run_p2(self, scenario_id: str, impl_type: str) -> P2Measurements:
        from harness.adapters.ms_agent.p2_measure import measure_p2
        return measure_p2()

    def _run_p3(self, scenario_id: str, impl_type: str) -> P3Measurements:
        from harness.adapters.ms_agent.p3_measure import measure_p3
        return measure_p3(run_id=f"p3-{scenario_id}-{impl_type}")

    def _run_p4(self, scenario_id: str, impl_type: str) -> P4Measurements:
        from harness.adapters.ms_agent.p4_measure import measure_p4
        return measure_p4()

    def _run_p5(self, scenario_id: str, impl_type: str) -> P5Measurements:
        from harness.adapters.ms_agent.p5_measure import measure_p5
        return measure_p5()
