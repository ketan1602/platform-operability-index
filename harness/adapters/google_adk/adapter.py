"""Google ADK adapter — F4.

Pillar methods for the baseline scenarios (GEW, TCW). Routing, the measured
scenarios (RLC, SMA, AHQ) and scoring live in BaseAdapter.
"""
from __future__ import annotations

import structlog

from harness.adapters.shared.base_adapter import BaseAdapter
from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements, P4Measurements, P5Measurements

log = structlog.get_logger()
_EXPECTED_STEPS = {
    "fetch_system_a", "fetch_system_b",
    "score_risk", "hitl_gate",
    "crm_write", "assemble_audit",
}


class GoogleADKAdapter(BaseAdapter):
    framework_id = "F4"
    package = "google-adk"

    def _run_p1(self, scenario_id: str, impl_type: str) -> P1Measurements:
        if scenario_id.upper() == "TCW":
            from harness.adapters.shared.tcw_p1 import validate_tcw_t1
            validate_tcw_t1("F4", impl_type)
        if impl_type == "idiomatic":
            from scenarios.gew.implementations.google_adk.idiomatic.workflow import run_workflow
        else:
            from scenarios.gew.implementations.google_adk.fixed.workflow import run_workflow

        workflow_id = f"p1-baseline-{scenario_id}-{impl_type}"
        result = run_workflow(workflow_id)
        step_log = set(result.get("step_log", []))
        missing = _EXPECTED_STEPS - step_log
        if missing:
            raise RuntimeError(f"P1-T1 ({impl_type}) failed — missing steps: {missing}")

        log.info("p1_t1_pass", impl_type=impl_type, step_log=sorted(step_log))

        # P1-T2: InMemorySessionService is process-local — cross-process resume
        #         requires a custom persistent session backend (Redis/Postgres).
        #         manual_watchdog_required=True: operator must restart and replay.
        # P1-T3: CRM tool uses an idempotency_key → duplicate_tool_calls=0.
        # P1-T4: InMemorySessionService state is JSON-serialisable → "parseable".
        # P1-T5: No distributed lock in InMemorySessionService → "not_prevented".
        # custom_code_lines_to_reach_score_3 ≈ 80 LOC for a persistent session backend.
        return P1Measurements(
            resume_latency_ms=None,
            steps_re_executed_on_resume=None,
            duplicate_tool_calls_on_mid_write=0,
            checkpoint_format="parseable",
            concurrent_resume_collision="not_prevented",
            manual_watchdog_required=True,
            custom_code_lines_to_reach_score_3=80,
        )

    def _run_p2(self, scenario_id: str, impl_type: str) -> P2Measurements:
        from harness.adapters.google_adk.p2_measure import measure_p2
        return measure_p2()

    def _run_p3(self, scenario_id: str, impl_type: str) -> P3Measurements:
        from harness.adapters.google_adk.p3_measure import measure_p3
        return measure_p3(run_id=f"p3-{scenario_id}-{impl_type}")

    def _run_p4(self, scenario_id: str, impl_type: str) -> P4Measurements:
        from harness.adapters.google_adk.p4_measure import measure_p4
        return measure_p4()

    def _run_p5(self, scenario_id: str, impl_type: str) -> P5Measurements:
        from harness.adapters.google_adk.p5_measure import measure_p5
        return measure_p5()
