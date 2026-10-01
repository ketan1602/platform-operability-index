"""UI server configuration — every value comes from the environment."""
from __future__ import annotations
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FRAMEWORKS = ("F1", "F2", "F3", "F4", "F5")
BASELINE_SCENARIOS = ("GEW", "TCW")
MEASURED_SCENARIOS = ("RLC", "SMA", "AHQ")
SCENARIOS = BASELINE_SCENARIOS + MEASURED_SCENARIOS
IMPLS = ("fixed", "idiomatic")
MODES = ("live", "dry_run")

# Env vars a live (non-DRY_RUN) run cannot proceed without.
LIVE_REQUIRED_ENV = ("AIREFINERY_API_KEY", "AIREFINERY_BASE_URL", "AIREFINERY_SDK_VERSION")
# Measured scenarios additionally need the real backing services (./infra.sh up).
INFRA_REQUIRED_ENV = ("POSTGRES_URL", "RABBITMQ_URL", "NEO4J_URI", "OTEL_EXPORTER_OTLP_ENDPOINT",
                      "JAEGER_QUERY_URL")


def results_root() -> Path:
    return Path(os.environ.get("POI_RESULTS_DIR", REPO_ROOT / "results" / "runs"))


def results_dir(mode: str) -> Path:
    """Live and dry-run results are kept apart so canned fixtures never mix into live scores."""
    return results_root() / mode


def missing_live_env() -> list[str]:
    return [k for k in LIVE_REQUIRED_ENV if not os.environ.get(k)]


def missing_infra_env() -> list[str]:
    return [k for k in INFRA_REQUIRED_ENV if not os.environ.get(k)]
