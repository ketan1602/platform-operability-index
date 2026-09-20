"""POI score matrix CLI.

Reads all YAML run results and prints a per-framework, per-scenario score table.

Usage:
    python analysis/score_matrix.py [--results-dir path] [--output table|csv]
"""
from __future__ import annotations

import argparse
import csv
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
_CSV_OUTPUT = _SCRIPT_DIR / "poi_score_matrix.csv"
_COLUMNS = ["framework_id", "scenario_id", "impl_type", "p1", "p2", "p3", "p4", "p5", "poi_total"]
_SKIP_FILES = {"summary.yaml"}
_PILLARS = ["p1", "p2", "p3", "p4", "p5"]


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


def _build_rows(records: list) -> list[dict]:
    groups: dict = defaultdict(lambda: {c: None for c in _COLUMNS})

    for r in records:
        m = r.run_metadata
        key = (m.framework_id.value, m.scenario_id.value, m.implementation_type.value)
        g = groups[key]
        g["framework_id"] = m.framework_id.value
        g["scenario_id"] = m.scenario_id.value
        g["impl_type"] = m.implementation_type.value
        for p in _PILLARS:
            val = getattr(r.pillar_scores, p)
            if val is not None:
                g[p] = val

    rows = list(groups.values())
    for row in rows:
        scores = [row[p] for p in _PILLARS if row[p] is not None]
        row["poi_total"] = sum(scores)
    return rows


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("No results found.")
        return
    data = [[r.get(c, "") for c in _COLUMNS] for r in rows]
    if _HAS_TABULATE:
        print(_tabulate(data, headers=_COLUMNS, tablefmt="github"))
    else:
        print("\t".join(_COLUMNS))
        for row in data:
            print("\t".join("" if v is None else str(v) for v in row))


def _write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("csv_written", path=str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="POI score matrix")
    parser.add_argument("--results-dir", type=Path, default=_DEFAULT_RESULTS)
    parser.add_argument("--output", choices=["table", "csv"], default="table")
    args = parser.parse_args()

    records = _load_results(args.results_dir)
    rows = _build_rows(records)
    _print_table(rows)
    if args.output == "csv":
        _write_csv(rows, _CSV_OUTPUT)


if __name__ == "__main__":
    main()
