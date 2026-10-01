"""LangGraph adapter — F1.

Pillar methods for the baseline scenarios (GEW, TCW). Routing, the measured
scenarios (RLC, SMA, AHQ) and scoring live in BaseAdapter.
"""
from __future__ import annotations

import structlog

from harness.adapters.shared.base_adapter import BaseAdapter
from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements, P4Measurements, P5Measurements

log = structlog.get_logger()


class LangGraphAdapter(BaseAdapter):
    framework_id = "F1"
    package = "langgraph"

    def _run_p1(self, scenario_id: str, impl_type: str) -> P1Measurements:
        if scenario_id.upper() == "TCW":
            from harness.adapters.shared.tcw_p1 import validate_tcw_t1
            validate_tcw_t1("F1", impl_type)
        from harness.adapters.langgraph.p1_measure import measure_p1
        return measure_p1(impl_type=impl_type)

    def _run_p2(self, scenario_id: str, impl_type: str) -> P2Measurements:
        from harness.adapters.langgraph.p2_measure import measure_p2
        return measure_p2()

    def _run_p3(self, scenario_id: str, impl_type: str) -> P3Measurements:
        from harness.adapters.langgraph.p3_measure import measure_p3
        return measure_p3(run_id=f"p3-{scenario_id}-{impl_type}")

    def _run_p4(self, scenario_id: str, impl_type: str) -> P4Measurements:
        from harness.adapters.langgraph.p4_measure import measure_p4
        return measure_p4()

    def _run_p5(self, scenario_id: str, impl_type: str) -> P5Measurements:
        from harness.adapters.langgraph.p5_measure import measure_p5
        return measure_p5()
