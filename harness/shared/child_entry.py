"""Child-process entry point for one scenario trial.

    python -m harness.shared.child_entry <module:function> '<json kwargs>'

Prints exactly one ``POI_RESULT {json}`` line. If the result carries ``"hold": true``
the process then blocks forever, simulating a worker waiting on a human — the
parent harness SIGKILLs it.
"""
from __future__ import annotations
import asyncio
import importlib
import inspect
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

RESULT_PREFIX = "POI_RESULT "


def _call(target: str, kwargs: dict) -> dict:
    module_name, func_name = target.split(":")
    func = getattr(importlib.import_module(module_name), func_name)
    result = func(**kwargs)
    return asyncio.run(result) if inspect.iscoroutine(result) else result


def main() -> None:
    from harness.shared import token_tracker
    token_tracker.install()
    target, raw = sys.argv[1], sys.argv[2]
    try:
        result = _call(target, json.loads(raw))
    except BaseException as exc:  # the trial's outcome, reported to the parent
        result = {"stop": "exception", "signal": type(exc).__name__, "error": str(exc)[:500]}
    print(RESULT_PREFIX + json.dumps(result, default=str), flush=True)
    if result.get("hold"):
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
