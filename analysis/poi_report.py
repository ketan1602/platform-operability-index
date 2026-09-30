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
import sys
from collections import defaultdict
from pathlib import Path

import structlog

_SCRIPT_DIR = Path(__file__).parent
# Allows `python analysis/poi_report.py` as well as `-m analysis.poi_report`.
sys.path.insert(0, str(_SCRIPT_DIR.parent))

from analysis.sensitivity import compute_sensitivity  # noqa: E402

log = structlog.get_logger(__name__)
_DEFAULT_RESULTS = _SCRIPT_DIR.parent / "results" / "runs"
_PILLARS = ["p1", "p2", "p3", "p4", "p5"]
_SKIP = {"summary.yaml"}
_FW_NAMES = {
    "F1": "LangGraph",
    "F2": "AutoGen (MS)",
    "F3": "OpenAI SDK",
    "F4": "Google ADK",
    "F5": "Strands",
}


def _load(results_dir: Path) -> list:
    from harness.shared.measurement import RunResult
    records = []
    for f in sorted(results_dir.glob("**/*.yaml")):
        if f.name in _SKIP:
            continue
        try:
            records.append(RunResult.from_yaml(f.read_text()))
        except Exception as exc:
            log.warning("result_parse_failed", file=f.name, error=str(exc))
    return records


def _score_matrix(records: list) -> dict[str, dict[str, float]]:
    sums: dict = defaultdict(lambda: defaultdict(list))
    for r in records:
        fid = r.run_metadata.framework_id.value
        for p in _PILLARS:
            v = getattr(r.pillar_scores, p)
            if v is not None:
                sums[fid][p].append(v)
    matrix: dict = {}
    for fid, pillars in sorted(sums.items()):
        matrix[fid] = {p: round(sum(vs) / len(vs)) for p, vs in pillars.items()}
        matrix[fid]["poi_total"] = sum(matrix[fid].get(p, 0) for p in _PILLARS)
    return matrix


def _ot_table(records: list) -> dict[str, int]:
    seen: dict = {}
    for r in records:
        fid = r.run_metadata.framework_id.value
        sc  = r.run_metadata.scenario_id.value
        imp = r.run_metadata.implementation_type.value
        key = (fid, sc, imp)
        if key not in seen:
            seen[key] = r.operability_tax.ot_loc
    totals: dict = defaultdict(list)
    for (fid, _, _), loc in seen.items():
        totals[fid].append(loc)
    return {fid: max(locs) for fid, locs in sorted(totals.items())}


def _print_score_matrix(matrix: dict) -> None:
    header = f"{'Framework':<18} {'P1':>4} {'P2':>4} {'P3':>4} {'P4':>4} {'P5':>4} {'POI':>5}"
    sep    = "-" * len(header)
    print("\n=== POI Score Matrix (0–3 per pillar, max 15) ===")
    print(header)
    print(sep)
    for fid, scores in matrix.items():
        name = _FW_NAMES.get(fid, fid)
        row  = f"{name:<18}"
        for p in _PILLARS:
            row += f" {scores.get(p, '-'):>4}"
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


def build_report(results_dir: Path, samples: int = 1000) -> dict:
    """Structured report for API consumers; empty sections when no results exist."""
    records = _load(results_dir)
    if not records:
        return {"run_count": 0, "names": _FW_NAMES, "matrix": {}, "ot": {},
                "ranking": [], "sensitivity": None}
    matrix = _score_matrix(records)
    ot = _ot_table(records)
    return {
        "run_count": len(records),
        "names": _FW_NAMES,
        "matrix": matrix,
        "ot": ot,
        "ranking": _rank(matrix, ot),
        "sensitivity": compute_sensitivity(matrix, n=samples),
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

    matrix = _score_matrix(records)
    ot     = _ot_table(records)

    _print_score_matrix(matrix)
    _print_ot_table(ot, matrix)
    _print_ranking(matrix, ot)
    if not args.no_sensitivity:
        _print_sensitivity(compute_sensitivity(matrix))
    print()


if __name__ == "__main__":
    main()
