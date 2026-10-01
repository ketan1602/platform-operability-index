"""Shared adapter behaviour: route a run to its measurements, score, and assemble the result.

Baseline scenarios (GEW, TCW) in DRY_RUN call the subclass's `_run_p1`…`_run_p5`.
In live mode, GEW and TCW also run their measured harnesses (SIGKILL+resume for P1;
fault injection + Jaeger for P2/P3). Legacy measured scenarios (RLC, SMA, AHQ) always
use the framework-agnostic trial; P4/P5 come from the subclass as usual.
"""
from __future__ import annotations
import importlib
import importlib.metadata
import os

import structlog

from harness.shared.measurement import OperabilityTax, PillarScores, RunMetadata, RunResult
from harness.shared.scoring import score_p1, score_p2, score_p3, score_p4, score_p5

log = structlog.get_logger()

PILLARS = ("p1", "p2", "p3", "p4", "p5")
_SCORERS = {"p1": score_p1, "p2": score_p2, "p3": score_p3, "p4": score_p4, "p5": score_p5}
_LOC_FIELDS = ("custom_code_lines_to_reach_score_3", "custom_code_lines_for_isolation",
               "custom_exporter_loc", "template_loc")
# Measured scenario -> the pillars it produces evidence for.
# GEW and TCW baselines run via the subclass _run_* methods in DRY_RUN; in live mode
# the harness.scenarios.{gew,tcw} modules provide richer measured evidence.
MEASURED = {
    "RLC": ("p2",),
    "SMA": ("p2", "p3"),
    "AHQ": ("p1",),
    "GEW": ("p1",),
    "TCW": ("p2", "p3"),
}
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
        dry_run = os.environ.get("DRY_RUN") == "true"
        # GEW/TCW measured harnesses require live infra; skip in DRY_RUN so baselines work.
        use_measured = scenario in MEASURED and not dry_run
        if use_measured:
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
