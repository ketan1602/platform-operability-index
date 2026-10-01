"""Shared adapter behaviour: route a run to its measurements, score, and assemble the result.

Baseline scenarios (GEW, TCW) call the subclass's `_run_p1`…`_run_p5`. Measured
scenarios (RLC, SMA, AHQ) run the framework-agnostic trials in harness.scenarios,
which only measure the pillars they stress; P4/P5 come from the subclass as usual.
"""
from __future__ import annotations
import importlib
import importlib.metadata

import structlog

from harness.shared.measurement import OperabilityTax, PillarScores, RunMetadata, RunResult
from harness.shared.scoring import score_p1, score_p2, score_p3, score_p4, score_p5

log = structlog.get_logger()

PILLARS = ("p1", "p2", "p3", "p4", "p5")
_SCORERS = {"p1": score_p1, "p2": score_p2, "p3": score_p3, "p4": score_p4, "p5": score_p5}
_LOC_FIELDS = ("custom_code_lines_to_reach_score_3", "custom_code_lines_for_isolation",
               "custom_exporter_loc", "template_loc")
# Measured scenario -> the pillars it produces evidence for.
MEASURED = {"RLC": ("p2",), "SMA": ("p2", "p3"), "AHQ": ("p1",)}
_STATIC = ("p4", "p5")  # framework properties, identical in every scenario


def _dump(meas) -> dict:
    return meas.model_dump() if hasattr(meas, "model_dump") else meas.dict()


def _ot_loc(meas) -> int:
    return sum(getattr(meas, f, 0) or 0 for f in _LOC_FIELDS)


class BaseAdapter:
    framework_id: str = ""
    package: str = ""

    @property
    def framework_version(self) -> str:
        try:
            return importlib.metadata.version(self.package)
        except importlib.metadata.PackageNotFoundError:
            return "unknown"

    def run(self, meta: RunMetadata, pillar: str, scenario_id: str, impl_type: str) -> RunResult:
        wanted = PILLARS if pillar == "all" else (pillar,)
        measured, notes = self._measure(scenario_id.upper(), impl_type, wanted)
        scores, raw, loc = PillarScores(), {}, 0
        for p, meas in measured.items():
            raw[p] = _dump(meas)
            loc += _ot_loc(meas)
            setattr(scores, p, _SCORERS[p](meas))
        return RunResult(run_metadata=meta, pillar_scores=scores,
                         operability_tax=OperabilityTax(ot_loc=loc), raw_measurements=raw, notes=notes)

    def _measure(self, scenario: str, impl_type: str, wanted: tuple) -> tuple[dict, str]:
        out: dict = {}
        notes = ""
        if scenario in MEASURED:
            module = importlib.import_module(f"harness.scenarios.{scenario.lower()}")
            evidence = module.measure(self.framework_id)
            notes = evidence.pop("notes", "")
            out.update({p: m for p, m in evidence.items() if p in wanted})
            wanted = tuple(p for p in wanted if p in _STATIC)
        for p in wanted:
            try:
                out[p] = getattr(self, f"_run_{p}")(scenario, impl_type)
            except NotImplementedError as exc:
                log.info("pillar_skipped", pillar=p, reason=str(exc))
        return out, notes
