"""Child-side AHQ steps. `start` pauses at the approval gate; `resume` waits on RabbitMQ."""
from __future__ import annotations
import asyncio
import importlib
import inspect
import time

from harness.scenarios.common import impl_module
from harness.shared import approval_queue


def _call(fw: str, func: str, **kwargs) -> dict:
    result = getattr(importlib.import_module(impl_module("AHQ", fw)), func)(**kwargs)
    return asyncio.run(result) if inspect.iscoroutine(result) else result


def start(fw: str, run_id: str, workdir: str, **_) -> dict:
    return _call(fw, "start", run_id=run_id, workdir=workdir)


def resume(fw: str, run_id: str, workdir: str, start_at: float, resume_token: str | None = None, **_) -> dict:
    decision = approval_queue.wait_decision(run_id)
    # Barrier: both resumers act at the same instant, so the concurrency test is real.
    time.sleep(max(0.0, start_at - time.time()))
    return _call(fw, "resume", run_id=run_id, workdir=workdir,
                 approved=decision["approved"], resume_token=resume_token)
