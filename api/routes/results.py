"""Aggregated benchmark results: score matrix, OT-LOC, ranking, sensitivity."""
from __future__ import annotations

from fastapi import APIRouter, Query

from analysis.poi_report import build_report
from api.config import MODES, results_dir

router = APIRouter()


@router.get("/results")
def get_results(mode: str = Query("live", pattern=f"^({'|'.join(MODES)})$")) -> dict:
    report = build_report(results_dir(mode))
    return {"mode": mode, **report}
