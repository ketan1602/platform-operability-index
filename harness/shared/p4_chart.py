"""Pod spec diff probe for P4: detect framework-specific env vars in Helm charts.

Parses the rendered deployment template, extracts all env var names, and
returns those not present in the cross-framework baseline set.  The baseline
contains env vars every agent pod needs regardless of framework.
"""
from __future__ import annotations
import re
from pathlib import Path

_ENV_NAME_RE = re.compile(r"^\s+-\s+name:\s+([A-Z][A-Z0-9_]+)\s*$", re.MULTILINE)

_BASELINE_ENV = frozenset({
    "AIREFINERY_API_KEY",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "POI_FRAMEWORK",
    "POI_TENANT",
})


def probe_chart_hacks(chart_dir: Path) -> list[str]:
    """Return env var names in chart templates that are not in the baseline set.

    Reads all *.yaml files under chart_dir/templates/, extracts uppercase env var
    names, and subtracts the baseline.  No Helm binary required — the names in
    templates are always static strings even when values use expressions.
    """
    templates = chart_dir / "templates"
    if not templates.is_dir():
        return []
    found: set[str] = set()
    for f in templates.rglob("*.yaml"):
        for name in _ENV_NAME_RE.findall(f.read_text()):
            found.add(name)
    return sorted(found - _BASELINE_ENV)
