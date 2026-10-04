"""K8s-fit sub-tests shared across all framework P4 measurements.

test_lazy_init: verifies the framework does not eagerly check credentials at import time.
test_sigterm: verifies the process exits cleanly within 3s when SIGTERM is sent.
"""
from __future__ import annotations
import os
import signal
import subprocess
import sys
import time

import structlog

log = structlog.get_logger(__name__)

_CRED_TOKENS = ("API", "KEY", "SECRET", "TOKEN")


def test_lazy_init(core_module: str) -> tuple[float, int]:
    """Import core_module in a subprocess without credential env vars.

    Returns (seconds, ms). seconds=-1.0 and ms=-1 if the import raised,
    indicating eager credential validation at import time.
    """
    env = {k: v for k, v in os.environ.items()
           if not any(tok in k.upper() for tok in _CRED_TOKENS)}
    code = (
        f"import time; t=time.monotonic(); "
        f"import {core_module}; "
        f"print(round(time.monotonic()-t, 2))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.info("k8s_fit.lazy_init_failed", module=core_module,
                     stderr=result.stderr[:200])
            return -1.0, -1
        secs = float(result.stdout.strip())
        return secs, int(secs * 1000)
    except Exception as exc:
        log.warning("k8s_fit.lazy_init_error", module=core_module, error=str(exc))
        return -1.0, -1


def test_sigterm(core_module: str) -> tuple[bool, int]:
    """Launch core_module in a subprocess then send SIGTERM after 1s.

    Returns (graceful, latency_ms). graceful=True if exits within 3s.
    latency_ms is measured from SIGTERM send to process exit.
    """
    code = f"import {core_module}; import time; time.sleep(60)"
    proc = subprocess.Popen([sys.executable, "-c", code])
    time.sleep(1)
    try:
        proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        return True, 0
    t0 = time.monotonic()
    try:
        proc.wait(timeout=3)
        return True, int((time.monotonic() - t0) * 1000)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        log.info("k8s_fit.sigterm_timeout", module=core_module)
        return False, 3000
