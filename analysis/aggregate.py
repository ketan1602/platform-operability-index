"""Aggregate run results into pillar scores.

Rules (v2):
  * P1–P3 come only from the scenarios that measure them (EVIDENCE). A framework with
    no measured-scenario results falls back to its baseline (GEW/TCW) values.
  * Within a scenario: median of the repeats (median_low, so scores stay integers and
    ties resolve conservatively); min/max are reported as the range.
  * Across scenarios: the minimum — operability fails at its weakest link.
  * An inconclusive repeat (score None, e.g. the model never looped) is excluded but counted.
"""
from __future__ import annotations
from collections import defaultdict
from statistics import median_low
from typing import Any, Optional

from harness.shared import scoring as _scoring
from harness.shared.pillar_models import (
    P1Measurements, P2Measurements, P3Measurements, P4Measurements,
    P5Measurements, P6Measurements, P7Measurements, P8Measurements,
)

_MODELS = {
    "p1": P1Measurements, "p2": P2Measurements, "p3": P3Measurements,
    "p4": P4Measurements, "p5": P5Measurements, "p6": P6Measurements,
    "p7": P7Measurements, "p8": P8Measurements,
}
_SCORERS = {
    "p1": _scoring.score_p1, "p2": _scoring.score_p2, "p3": _scoring.score_p3,
    "p4": _scoring.score_p4, "p5": _scoring.score_p5, "p6": _scoring.score_p6,
    "p7": _scoring.score_p7, "p8": _scoring.score_p8,
}

PILLARS = ("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8")
MEASURED = ("RLC", "SMA", "AHQ", "GEW", "TCW", "PORT", "DX", "SEC")
EVIDENCE = {
    "p1": ("AHQ", "GEW"),
    "p2": ("RLC", "SMA", "TCW"),
    "p3": ("SMA", "TCW"),
    "p6": ("PORT",),
    "p7": ("DX",),
    "p8": ("SEC",),
}
_LOC_FIELD = {"p1": "custom_code_lines_to_reach_score_3", "p2": "custom_code_lines_for_isolation",
              "p3": "custom_exporter_loc", "p4": "template_loc"}


def _tree():
    return defaultdict(lambda: defaultdict(lambda: defaultdict(list)))


def _rescore(pillar: str, raw: dict) -> Optional[Any]:
    """Re-score from raw measurement dict using current formulas; None on failure."""
    model_cls = _MODELS.get(pillar)
    scorer = _SCORERS.get(pillar)
    if not model_cls or not scorer:
        return None
    try:
        return scorer(model_cls(**raw))
    except Exception:
        return None


def _collect(records: list) -> tuple[dict, dict]:
    scores, locs = _tree(), _tree()
    for r in records:
        if r.error:
            continue
        fid, sc = r.run_metadata.framework_id.value, r.run_metadata.scenario_id.value
        for p in PILLARS:
            if p not in r.raw_measurements:
                continue
            raw = r.raw_measurements[p]
            score = _rescore(p, raw)
            if score is None:
                score = getattr(r.pillar_scores, p)
            scores[fid][p][sc].append(score)
            if p in _LOC_FIELD:
                locs[fid][p][sc].append(raw.get(_LOC_FIELD[p]) or 0)
    return scores, locs


def _cell(values: list) -> dict:
    vals = [v for v in values if v is not None]
    return {"median": median_low(vals) if vals else None, "min": min(vals, default=None),
            "max": max(vals, default=None), "n": len(vals), "inconclusive": len(values) - len(vals)}


def _scenarios(fid_scores: dict, pillar: str, measured: bool) -> list[str]:
    available = list(fid_scores[pillar])
    if measured and pillar in EVIDENCE:
        return [sc for sc in EVIDENCE[pillar] if sc in available]
    return available


def aggregate(records: list) -> dict:
    """Return {fid: {"scores": {p: int|None}, "evidence": {p: {sc: cell}}, "source": str, "ot_loc": int}}."""
    scores, locs = _collect(records)
    out = {}
    for fid in sorted(scores):
        measured = any(sc in MEASURED for p in scores[fid] for sc in scores[fid][p])
        entry = {"scores": {}, "evidence": {}, "source": "measured" if measured else "baseline", "ot_loc": 0}
        for p in PILLARS:
            cells = {sc: _cell(scores[fid][p][sc]) for sc in _scenarios(scores[fid], p, measured)}
            medians = [c["median"] for c in cells.values() if c["median"] is not None]
            entry["scores"][p] = min(medians) if medians else None
            entry["evidence"][p] = cells
            entry["ot_loc"] += max((max(locs[fid][p][sc]) for sc in cells if locs[fid][p][sc]), default=0)
        entry["scores"]["poi_total"] = sum(v for k, v in entry["scores"].items() if v is not None)
        out[fid] = entry
    return out
