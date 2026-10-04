"""Aggregated benchmark results: score matrix, OT-LOC, ranking, sensitivity."""
from __future__ import annotations

from fastapi import APIRouter, Query

from analysis.poi_report import build_report, list_runs
from api.config import MODES, results_dir

router = APIRouter()

_RUN_PATTERN = r"^\d{8}T\d{6}Z$"


@router.get("/results")
def get_results(
    mode: str = Query("live", pattern=f"^({'|'.join(MODES)})$"),
    run: str | None = Query(None, pattern=_RUN_PATTERN),
) -> dict:
    report = build_report(results_dir(mode), run=run)
    return {"mode": mode, **report}


@router.get("/run-list")
def get_run_list(
    mode: str = Query("live", pattern=f"^({'|'.join(MODES)})$"),
) -> dict:
    return {"mode": mode, "runs": list_runs(results_dir(mode))}
