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
from harness.shared.scoring import score_p1, score_p2, score_p3, score_p4, score_p5, score_p6, score_p7, score_p8, score_p9

log = structlog.get_logger()

PILLARS = ("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9")
_SCORERS = {
    "p1": score_p1, "p2": score_p2, "p3": score_p3,
    "p4": score_p4, "p5": score_p5,
    "p6": score_p6, "p7": score_p7, "p8": score_p8, "p9": score_p9,
}
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
    "PORT": ("p6",),
    "DX": ("p7",),
    "SEC": ("p8",),
    "OPS": ("p9",),
}
_STATIC = ("p4", "p5")  # framework properties, identical in every scenario


def _dump(meas) -> dict:
    return meas.model_dump() if hasattr(meas, "model_dump") else meas.dict()


def _ot_loc(meas) -> int:
    return sum(getattr(meas, f, 0) or 0 for f in _LOC_FIELDS)


def _ot_hack_costs(meas) -> tuple[float, float]:
    """Return (one_time_hrs, recurring_hrs_per_yr) from P4 HackRecord list."""
    hacks = getattr(meas, "framework_specific_hacks_required", None) or []
    ot = sum(getattr(h, "cost_hrs", 0) for h in hacks)
    rec = sum(getattr(h, "recurring_hrs_per_yr", 0) for h in hacks)
    return ot, rec


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
        measured, notes, tokens = self._measure(scenario_id.upper(), impl_type, wanted)
        scores, raw, loc, ot_hrs, ot_rec = PillarScores(), {}, 0, 0.0, 0.0
        for p, meas in measured.items():
            raw[p] = _dump(meas)
            loc += _ot_loc(meas)
            hack_hrs, hack_rec = _ot_hack_costs(meas)
            ot_hrs += hack_hrs
            ot_rec += hack_rec
            setattr(scores, p, _SCORERS[p](meas))
        return RunResult(run_metadata=meta, pillar_scores=scores,
                         operability_tax=OperabilityTax(ot_loc=loc, ot_hrs=ot_hrs,
                                                        ot_recurring_hrs_per_yr=ot_rec),
                         raw_measurements=raw, finops=tokens, notes=notes)

    def _measure(self, scenario: str, impl_type: str, wanted: tuple) -> tuple[dict, str, dict]:
        out: dict = {}
        notes = ""
        tokens: dict = {}
        dry_run = os.environ.get("DRY_RUN") == "true"
        # GEW/TCW measured harnesses require live infra; skip in DRY_RUN so baselines work.
        use_measured = scenario in MEASURED and not dry_run
        if use_measured:
            from harness.shared import child as _child
            _child.reset_ledger_registry()
            module = importlib.import_module(f"harness.scenarios.{scenario.lower()}")
            evidence = module.measure(self.framework_id)
            notes = evidence.pop("notes", "")
            out.update({p: m for p, m in evidence.items() if p in wanted})
            wanted = tuple(p for p in wanted if p in _STATIC)
            tokens = _child.collect_tokens()
        for p in wanted:
            runner = getattr(self, f"_run_{p}", None)
            if runner is None:
                continue
            try:
                out[p] = runner(scenario, impl_type)
            except NotImplementedError as exc:
                log.info("pillar_skipped", pillar=p, reason=str(exc))
        return out, notes, tokens

    @staticmethod
    def _read_tokens() -> dict:
        from pathlib import Path
        from harness.shared import ledger as _ledger
        path_str = os.environ.get(_ledger.LEDGER_ENV)
        if not path_str:
            return {}
        entries = _ledger.read(Path(path_str))
        return _ledger.sum_tokens(entries)
