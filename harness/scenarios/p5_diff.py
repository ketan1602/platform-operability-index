"""Structured diff of before/after P5 scenario result YAMLs.

Pairs result files by (fw, scenario, impl) and compares pillar_scores and
raw_measurements to produce empirical api_breaking / schema_breaking counts.
"""
from __future__ import annotations
import re
from pathlib import Path

import yaml

_FW_RE = re.compile(r"_(F[1-5])_([A-Z]+)_([a-z]+)_")

_SCHEMA_PILLARS = frozenset({"p1"})
_API_PILLARS = frozenset({"p2", "p3", "p6", "p7"})

_BOOL_GOOD = frozenset({
    "runaway_loop_contained_by_default",
    "alert_fired_without_custom_code",
    "hitl_verified",
    "context_isolation_verified",
    "tool_scope_enforced",
    "oss_stack_viable",
})
_INT_BURDEN = frozenset({
    "custom_exporter_loc",
    "custom_code_lines_for_isolation",
    "custom_code_lines_to_reach_score_3",
})
_LIST_GOOD = frozenset({"required_attributes_emitted_by_default"})


def _key(filename: str) -> tuple[str, str, str] | None:
    m = _FW_RE.search(filename)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def _load_dir(d: Path) -> dict[tuple, dict]:
    out: dict[tuple, dict] = {}
    for f in d.glob("*.yaml"):
        k = _key(f.name)
        if k:
            try:
                out[k] = yaml.safe_load(f.read_text()) or {}
            except Exception:
                pass
    return out


def _flatten(raw: dict) -> dict:
    flat: dict = {}
    for pillar, fields in raw.items():
        if isinstance(fields, dict):
            for field, val in fields.items():
                flat[f"{pillar}.{field}"] = val
    return flat


def _score_regression(b: dict, a: dict) -> tuple[int, int]:
    api = schema = 0
    for pillar, bval in b.items():
        if pillar == "poi_total":
            continue
        aval = a.get(pillar, bval)
        if isinstance(bval, (int, float)) and isinstance(aval, (int, float)) and aval < bval:
            if pillar in _SCHEMA_PILLARS:
                schema += 1
            elif pillar in _API_PILLARS:
                api += 1
    return api, schema


def _field_regressions(key: tuple, bf: dict, af: dict) -> list[dict]:
    out = []
    for fk, bval in bf.items():
        field = fk.split(".", 1)[-1]
        aval = af.get(fk, bval)
        if bval == aval:
            continue
        regressed = False
        if field in _BOOL_GOOD and bval is True and aval is False:
            regressed = True
        elif field in _INT_BURDEN and isinstance(bval, int) and isinstance(aval, int) and aval > bval:
            regressed = True
        elif field in _LIST_GOOD and isinstance(bval, list) and isinstance(aval, list) and len(aval) < len(bval):
            regressed = True
        if regressed:
            out.append({"fw": key[0], "scenario": key[1], "field": fk, "before": bval, "after": aval})
    return out


def diff(before_dir: Path, after_dir: Path) -> dict:
    """Compare before/after result dirs. Returns P5 field dict with structured regressions."""
    before = _load_dir(before_dir)
    after = _load_dir(after_dir)

    failures = api_breaks = schema_breaks = 0
    regressions: list[dict] = []

    for key, bdata in before.items():
        if key not in after:
            failures += 1
            continue
        adata = after[key]

        if adata.get("error") and not bdata.get("error"):
            failures += 1
            api_breaks += 1
            continue

        api, schema = _score_regression(
            bdata.get("pillar_scores", {}),
            adata.get("pillar_scores", {}),
        )
        api_breaks += api
        schema_breaks += schema
        if api + schema > 0:
            failures += 1

        bf = _flatten(bdata.get("raw_measurements", {}))
        af = _flatten(adata.get("raw_measurements", {}))
        regressions.extend(_field_regressions(key, bf, af))

    return {
        "harness_failures_after_upgrade": failures,
        "api_breaking_post_patch": api_breaks,
        "schema_breaking_post_patch": schema_breaks,
        "checkpoint_migration_required": schema_breaks > 0,
        "regressions": regressions,
    }
