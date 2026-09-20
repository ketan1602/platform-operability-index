"""Operability Tax summary CLI.

Reads all YAML run results and aggregates OT-LOC, one-time hours, and
recurring hours per framework.

Usage:
    python analysis/ot_summary.py [--results-dir path]
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import structlog

log = structlog.get_logger()

try:
    from tabulate import tabulate as _tabulate
    _HAS_TABULATE = True
except ImportError:
    _HAS_TABULATE = False

_SCRIPT_DIR = Path(__file__).parent
_DEFAULT_RESULTS = _SCRIPT_DIR.parent / "results" / "runs"
_SKIP_FILES = {"summary.yaml"}
_COLUMNS = ["framework", "ot_loc", "ot_hrs_one_time", "ot_recurring_hrs_per_yr"]


def _load_results(results_dir: Path) -> list:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))
    from harness.shared.measurement import RunResult

    records = []
    for yaml_file in sorted(results_dir.glob("**/*.yaml")):
        if yaml_file.name in _SKIP_FILES:
            continue
        try:
            records.append(RunResult.from_yaml(yaml_file.read_text()))
        except Exception as exc:
            log.warning("parse_error", file=str(yaml_file), error=str(exc))
    return records


def _aggregate(records: list) -> list[dict]:
    totals: dict = defaultdict(lambda: {"ot_loc": 0, "ot_hrs": 0.0, "ot_recurring": 0.0})

    for r in records:
        fid = r.run_metadata.framework_id.value
        totals[fid]["ot_loc"] += r.operability_tax.ot_loc
        totals[fid]["ot_hrs"] += r.operability_tax.ot_hrs
        totals[fid]["ot_recurring"] += r.operability_tax.ot_recurring_hrs_per_yr

    return [
        {
            "framework": fid,
            "ot_loc": t["ot_loc"],
            "ot_hrs_one_time": t["ot_hrs"],
            "ot_recurring_hrs_per_yr": t["ot_recurring"],
        }
        for fid, t in sorted(totals.items())
    ]


def _find_winner(rows: list[dict]) -> str | None:
    if not rows:
        return None
    return min(
        rows,
        key=lambda r: r["ot_loc"] + r["ot_hrs_one_time"] + r["ot_recurring_hrs_per_yr"],
    )["framework"]


def _print_summary(rows: list[dict]) -> None:
    if not rows:
        print("No results found.")
        return

    data = [[r[c] for c in _COLUMNS] for r in rows]
    if _HAS_TABULATE:
        print(_tabulate(data, headers=_COLUMNS, tablefmt="github"))
    else:
        print("\t".join(_COLUMNS))
        for row in data:
            print("\t".join(str(v) for v in row))

    winner = _find_winner(rows)
    if winner:
        print(f"\nLowest total OT: {winner}")


def main() -> None:
    parser = argparse.ArgumentParser(description="POI Operability Tax summary")
    parser.add_argument("--results-dir", type=Path, default=_DEFAULT_RESULTS)
    args = parser.parse_args()

    records = _load_results(args.results_dir)
    rows = _aggregate(records)
    _print_summary(rows)


if __name__ == "__main__":
    main()
