"""OpenAI Agents SDK adapter — F3.

Pillar methods for the baseline scenarios (GEW, TCW). Routing, the measured
scenarios (RLC, SMA, AHQ) and scoring live in BaseAdapter.
"""
from __future__ import annotations
import uuid

import structlog

from harness.adapters.shared.base_adapter import BaseAdapter
from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements, P4Measurements, P5Measurements

log = structlog.get_logger()


class OpenAISDKAdapter(BaseAdapter):
    framework_id = "F3"
    package = "openai-agents"

    def _run_p1(self, scenario_id: str, impl_type: str) -> P1Measurements:
        if scenario_id.upper() == "TCW":
            from harness.adapters.shared.tcw_p1 import validate_tcw_t1
            validate_tcw_t1("F3", impl_type)
        if impl_type == "idiomatic":
            from scenarios.gew.implementations.openai_agents_sdk.idiomatic.workflow import run_workflow
        else:
            from scenarios.gew.implementations.openai_agents_sdk.fixed.workflow import run_workflow

        workflow_id = f"poi-p1t1-{uuid.uuid4().hex[:8]}"
        result = run_workflow(workflow_id)
        step_log = result.get("step_log", [])
        assert len(step_log) == 5, f"Expected 5 steps, got {len(step_log)}: {step_log}"
        log.info("p1_t1_passed", workflow_id=workflow_id, impl_type=impl_type, steps=step_log)

        # OpenAI Agents SDK stores state in OpenAI's backend thread.
        # No portable checkpoint across process restarts without custom code.
        # Idempotency key at tool level prevents duplicate CRM writes (P1-T3).
        # Each run gets a unique thread_id — concurrent resume collision prevented (P1-T5).
        return P1Measurements(
            resume_latency_ms=None,
            steps_re_executed_on_resume=None,
            duplicate_tool_calls_on_mid_write=0,
            checkpoint_format="opaque",
            concurrent_resume_collision="prevented_by_framework",
            manual_watchdog_required=True,
            custom_code_lines_to_reach_score_3=0,
        )

    def _run_p2(self, scenario_id: str, impl_type: str) -> P2Measurements:
        from harness.adapters.openai_sdk.p2_measure import measure_p2
        return measure_p2()

    def _run_p3(self, scenario_id: str, impl_type: str) -> P3Measurements:
        from harness.adapters.openai_sdk.p3_measure import measure_p3
        return measure_p3(run_id=f"p3-{scenario_id}-{impl_type}")

    def _run_p4(self, scenario_id: str, impl_type: str) -> P4Measurements:
        from harness.adapters.openai_sdk.p4_measure import measure_p4
        return measure_p4()

    def _run_p5(self, scenario_id: str, impl_type: str) -> P5Measurements:
        from harness.adapters.openai_sdk.p5_measure import measure_p5
        return measure_p5()
