"""P5 empirical probe for AutoGen (F2)."""
from __future__ import annotations
import sys
import structlog
from harness.shared.pillar_models import P5Measurements
from harness.scenarios.p5_probe import probe

log = structlog.get_logger(__name__)

_PACKAGE = "autogen-agentchat"
_FW_ID = "F2"
_PROBE_SCENARIOS = [("TCW", "idiomatic"), ("SMA", "idiomatic")]


def measure_p5() -> P5Measurements:
    result = probe(
        package=_PACKAGE,
        fw_id=_FW_ID,
        python_exe=sys.executable,
        probe_scenarios=_PROBE_SCENARIOS,
        test_checkpoint=False,
    )
    log.info("p5.probed", fw=_FW_ID, **{k: v for k, v in result.items() if k != "version_before"})
    return P5Measurements(**result)
