"""Failure injection utilities — FI-1 through FI-4 (spec Section 3.2).

FI-1 / FI-2 kill a target process; FI-3 wraps a callable in a runaway
re-invocation loop; FI-4 poisons a credential config with a wrong tenant.
"""
from __future__ import annotations
import os
import signal
import time
from typing import Callable

import structlog

log = structlog.get_logger(__name__)


def inject_fi1(pid: int, delay_ms: int = 0) -> None:
    """FI-1: Send SIGTERM to *pid* after *delay_ms* milliseconds.

    Simulates a process kill that occurs after step N completes.
    """
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    log.info("fi1.kill", pid=pid, delay_ms=delay_ms)
    os.kill(pid, signal.SIGTERM)


def inject_fi2(pid: int, delay_ms: int = 0) -> None:
    """FI-2: Kill process during a write-side tool call.

    Mechanically identical to FI-1; the distinction is the caller's timing.
    """
    log.info("fi2.kill", pid=pid, delay_ms=delay_ms)
    inject_fi1(pid, delay_ms=delay_ms)


def inject_fi3_loop(fn: Callable, max_calls: int = 50) -> Callable:
    """FI-3: Return a wrapper that re-invokes *fn* up to *max_calls* times.

    Simulates a runaway loop to verify framework-level containment (P2).
    """
    call_count = 0

    def _looping(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        log.info("fi3.loop_call", call_count=call_count, max_calls=max_calls)
        result = fn(*args, **kwargs)
        if call_count < max_calls:
            return _looping(*args, **kwargs)
        log.info("fi3.loop_complete", total_calls=call_count)
        return result

    return _looping


def inject_fi4_credential(correct_config: dict, wrong_tenant_id: str) -> dict:
    """FI-4: Return a copy of *correct_config* with *tenant_id* replaced.

    Simulates cross-tenant credential injection; verifies credential-bleed
    detection (P2 — credential_bleed_events must remain 0).
    """
    poisoned = dict(correct_config)
    original = poisoned.get("tenant_id", "<unset>")
    poisoned["tenant_id"] = wrong_tenant_id
    log.info(
        "fi4.credential_poison",
        original_tenant=original,
        injected_tenant=wrong_tenant_id,
    )
    return poisoned
