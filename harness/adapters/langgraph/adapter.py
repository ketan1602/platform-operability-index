"""LangGraph adapter — M1 skeleton.

Pillar run methods raise NotImplementedError; wired up with real workflow
code in M2 under scenarios/gew/implementations/langgraph/.
"""
from __future__ import annotations

import importlib.metadata

import structlog

from harness.shared.measurement import (
    OperabilityTax,
    PillarScores,
    RunMetadata,
    RunResult,
)
from harness.shared.pillar_models import (
    P1Measurements,
    P2Measurements,
    P3Measurements,
    P4Measurements,
    P5Measurements,
)
from harness.shared.scoring import (
    score_p1,
    score_p2,
    score_p3,
    score_p4,
    score_p5,
)

log = structlog.get_logger()

_PILLAR_ORDER = ["p1", "p2", "p3", "p4", "p5"]
_SCORERS = {
    "p1": score_p1,
    "p2": score_p2,
    "p3": score_p3,
    "p4": score_p4,
    "p5": score_p5,
}
_LOC_FIELDS = (
    "custom_code_lines_to_reach_score_3",
    "custom_code_lines_for_isolation",
    "custom_exporter_loc",
    "template_loc",
)


def _ot_loc(meas) -> int:
    return sum(getattr(meas, f, 0) or 0 for f in _LOC_FIELDS)


def _dump(meas) -> dict:
    if hasattr(meas, "model_dump"):
        return meas.model_dump()
    return meas.dict()


class LangGraphAdapter:
    framework_id = "F1"

    @property
    def framework_version(self) -> str:
        try:
            return importlib.metadata.version("langgraph")
        except importlib.metadata.PackageNotFoundError:
            return "unknown"

    def run(
        self,
        meta: RunMetadata,
        pillar: str,
        scenario_id: str,
        impl_type: str,
    ) -> RunResult:
        pillars = _PILLAR_ORDER if pillar == "all" else [pillar]
        scores = PillarScores()
        raw: dict = {}
        total_loc = 0

        for p in pillars:
            meas, score, loc = self._run_and_score(p, scenario_id, impl_type)
            if meas is not None:
                raw[p] = _dump(meas)
                total_loc += loc
            if score is not None:
                setattr(scores, p, score)

        return RunResult(
            run_metadata=meta,
            pillar_scores=scores,
            operability_tax=OperabilityTax(ot_loc=total_loc),
            raw_measurements=raw,
        )

    def _run_and_score(self, pillar: str, scenario_id: str, impl_type: str):
        """Return (measurements | None, score | None, ot_loc: int)."""
        _runners = {
            "p1": self._run_p1,
            "p2": self._run_p2,
            "p3": self._run_p3,
            "p4": self._run_p4,
            "p5": self._run_p5,
        }
        try:
            meas = _runners[pillar](scenario_id, impl_type)
        except NotImplementedError as exc:
            log.info("pillar_skipped", pillar=pillar, reason=str(exc))
            return None, None, 0

        loc = _ot_loc(meas)
        try:
            score = _SCORERS[pillar](meas)
        except NotImplementedError:
            score = None
        return meas, score, loc

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
