"""POI benchmark report — article-ready tables.

Generates three tables from YAML run results:
  1. Score matrix: framework × pillar (P1-P5 + POI total), scenario-averaged.
  2. OT table: per-framework Operability Tax LOC (one representative value).
  3. Ranking: frameworks sorted by POI total descending, OT ascending.

Usage:
    python analysis/poi_report.py [--results-dir path]
"""
from __future__ import annotations
import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import structlog

_SCRIPT_DIR = Path(__file__).parent
# Allows `python analysis/poi_report.py` as well as `-m analysis.poi_report`.
sys.path.insert(0, str(_SCRIPT_DIR.parent))

from analysis.aggregate import aggregate  # noqa: E402
from analysis.sensitivity import compute_sensitivity  # noqa: E402

log = structlog.get_logger(__name__)
_DEFAULT_RESULTS = _SCRIPT_DIR.parent / "results" / "runs"
_PILLARS = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"]
_SKIP = {"summary.yaml"}
_FW_NAMES = {
    "F1": "LangGraph",
    "F2": "AutoGen (MS)",
    "F3": "OpenAI SDK",
    "F4": "Google ADK",
    "F5": "Strands",
}


_RUN_TS_RE = re.compile(r"^\d{8}T\d{6}Z")


def _load(results_dir: Path, run: str | None = None) -> list:
    from harness.shared.measurement import RunResult
    pattern = f"{run}_*.yaml" if run else "*.yaml"
    records = []
    for f in sorted(results_dir.glob(pattern)):
        if f.name in _SKIP:
            continue
        try:
            records.append(RunResult.from_yaml(f.read_text()))
        except Exception as exc:
            log.warning("result_parse_failed", file=f.name, error=str(exc))
    return records


def list_runs(results_dir: Path) -> list[dict]:
    """Return run batches newest-first: [{id, label, file_count}]."""
    counts: dict[str, int] = defaultdict(int)
    for f in results_dir.glob("*.yaml"):
        m = _RUN_TS_RE.match(f.name)
        if m:
            counts[m.group(0)] += 1
    def _label(ts: str) -> str:
        try:
            return datetime.strptime(ts, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            return ts
    return sorted(
        [{"id": k, "label": _label(k), "file_count": v} for k, v in counts.items()],
        key=lambda x: x["id"], reverse=True,
    )


def _score_matrix(agg: dict) -> dict[str, dict]:
    return {fid: e["scores"] for fid, e in agg.items()}


def _ot_table(agg: dict) -> dict[str, int]:
    return {fid: e["ot_loc"] for fid, e in agg.items()}


def _print_score_matrix(matrix: dict) -> None:
    header = f"{'Framework':<18} {'P1':>4} {'P2':>4} {'P3':>4} {'P4':>4} {'P5':>4} {'P6':>4} {'P7':>4} {'P8':>4} {'P9':>4} {'POI':>5}"
    sep    = "-" * len(header)
    print("\n=== POI Score Matrix (0–3 per pillar, max 27) ===")
    print(header)
    print(sep)
    for fid, scores in matrix.items():
        name = _FW_NAMES.get(fid, fid)
        row  = f"{name:<18}"
        for p in _PILLARS:
            v = scores.get(p)
            row += f" {'-' if v is None else v:>4}"
        row += f" {scores['poi_total']:>5}"
        print(row)


def _print_ot_table(ot: dict, matrix: dict) -> None:
    print("\n=== Operability Tax (custom LOC to reach production-grade operability) ===")
    header = f"{'Framework':<18} {'OT-LOC':>8} {'POI':>5}"
    print(header)
    print("-" * len(header))
    for fid, loc in sorted(ot.items(), key=lambda x: x[1]):
        name = _FW_NAMES.get(fid, fid)
        poi  = matrix.get(fid, {}).get("poi_total", "-")
        print(f"{name:<18} {loc:>8} {poi:>5}")


def _rank(matrix: dict, ot: dict) -> list[str]:
    return sorted(matrix, key=lambda f: (-matrix[f]["poi_total"], ot.get(f, 9999)))


def _print_ranking(matrix: dict, ot: dict) -> None:
    print("\n=== Ranking (primary: POI ↑, tiebreak: OT-LOC ↓) ===")
    for rank, fid in enumerate(_rank(matrix, ot), 1):
        name = _FW_NAMES.get(fid, fid)
        print(f"  #{rank}  {name:<18}  POI={matrix[fid]['poi_total']}  OT={ot.get(fid, 0)} LOC")


def _print_sensitivity(sens: dict) -> None:
    print(f"\n=== Sensitivity Analysis ({sens['samples']} Dirichlet weight samples) ===")
    print("Pairwise rank stability (% of weight vectors where equal-weight order holds):")
    for row in sens["pairs"]:
        na, nb = _FW_NAMES.get(row["a"], row["a"]), _FW_NAMES.get(row["b"], row["b"])
        print(f"  {na:>18} > {nb:<18}  {row['pct']:>3}%  [{row['tag']}]")
    print(f"Full ranking unchanged: {sens['full_rank_hold_pct']}% of draws")


def build_report(results_dir: Path, samples: int = 1000, run: str | None = None) -> dict:
    """Structured report for API consumers; empty sections when no results exist."""
    records = _load(results_dir, run=run)
    if not records:
        return {"run_count": 0, "names": _FW_NAMES, "matrix": {}, "ot": {},
                "ranking": [], "sensitivity": None, "evidence": {}, "source": {},
                "finops": {}, "perf": {}}
    agg = aggregate(records)
    matrix, ot = _score_matrix(agg), _ot_table(agg)
    return {
        "run_count": len(records),
        "errors": sum(1 for r in records if r.error),
        "evidence": {fid: e["evidence"] for fid, e in agg.items()},
        "source": {fid: e["source"] for fid, e in agg.items()},
        "names": _FW_NAMES,
        "matrix": matrix,
        "ot": ot,
        "ranking": _rank(matrix, ot),
        "sensitivity": compute_sensitivity(matrix, n=samples),
        "finops": {fid: e.get("finops", {}) for fid, e in agg.items()},
        "perf": {fid: e.get("perf", {}) for fid, e in agg.items()},
    }


def main() -> None:
    p = argparse.ArgumentParser(description="POI benchmark report")
    p.add_argument("--results-dir", type=Path, default=_DEFAULT_RESULTS)
    p.add_argument("--no-sensitivity", action="store_true",
                   help="Skip sensitivity analysis (faster)")
    args = p.parse_args()

    records = _load(args.results_dir)
    if not records:
        print("No results found.")
        return

    agg = aggregate(records)
    matrix, ot = _score_matrix(agg), _ot_table(agg)

    _print_score_matrix(matrix)
    _print_ot_table(ot, matrix)
    _print_ranking(matrix, ot)
    if not args.no_sensitivity:
        _print_sensitivity(compute_sensitivity(matrix))
    print()


if __name__ == "__main__":
    main()
