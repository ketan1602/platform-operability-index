"""Append-only evidence ledger shared by a trial's processes.

Tools record every invocation here. Because each line is flushed as it is written,
the record survives a SIGKILL and can be read by the parent harness afterwards.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path

LEDGER_ENV = "POI_LEDGER"


def record(event: str, **fields) -> None:
    path = os.environ.get(LEDGER_ENV)
    if not path:
        raise RuntimeError(f"{LEDGER_ENV} is not set — tools must run inside a harness trial")
    line = json.dumps({"event": event, "pid": os.getpid(), "ts": time.time(), **fields})
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def count(entries: list[dict], event: str) -> int:
    return sum(1 for e in entries if e["event"] == event)


def sum_tokens(entries: list[dict]) -> dict:
    """Sum all llm_usage events into {input_tokens, output_tokens, total_tokens}."""
    inp = sum(e.get("input_tokens", 0) for e in entries if e.get("event") == "llm_usage")
    out = sum(e.get("output_tokens", 0) for e in entries if e.get("event") == "llm_usage")
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out}
