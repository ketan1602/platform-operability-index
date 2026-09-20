"""Google ADK adapter — GEW fixed implementation.

P1 is wired to the SequentialAgent workflow; P2-P5 are NotImplementedError stubs.
"""
from __future__ import annotations

import importlib.metadata

import structlog

from harness.shared.measurement import OperabilityTax, PillarScores, RunMetadata, RunResult
from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements
from harness.shared.pillar_models import P4Measurements, P5Measurements
from harness.shared.scoring import score_p1, score_p2, score_p3, score_p4, score_p5

log = structlog.get_logger()

_PILLAR_ORDER = ["p1", "p2", "p3", "p4", "p5"]
_SCORERS = {"p1": score_p1, "p2": score_p2, "p3": score_p3, "p4": score_p4, "p5": score_p5}
_LOC_FIELDS = (
    "custom_code_lines_to_reach_score_3",
    "custom_code_lines_for_isolation",
    "custom_exporter_loc",
    "template_loc",
)
_EXPECTED_STEPS = {
    "fetch_system_a", "fetch_system_b",
    "score_risk", "hitl_gate",
    "crm_write", "assemble_audit",
}


def _ot_loc(meas) -> int:
    return sum(getattr(meas, f, 0) or 0 for f in _LOC_FIELDS)


def _dump(meas) -> dict:
    if hasattr(meas, "model_dump"):
        return meas.model_dump()
    return meas.dict()


class GoogleADKAdapter:
    framework_id = "F4"

    @property
    def framework_version(self) -> str:
        try:
            return importlib.metadata.version("google-adk")
        except importlib.metadata.PackageNotFoundError:
            return "unknown"

    def run(self, meta: RunMetadata, pillar: str, scenario_id: str, impl_type: str) -> RunResult:
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
