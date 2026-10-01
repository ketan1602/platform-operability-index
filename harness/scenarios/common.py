"""Shared plumbing for the measured scenarios (RLC, SMA, AHQ)."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path

IMPL_DIRS = {"F1": "langgraph", "F2": "ms_agent", "F3": "openai_agents_sdk",
             "F4": "google_adk", "F5": "strands_agents"}


def impl_module(scenario: str, fw: str) -> str:
    return f"scenarios.{scenario.lower()}.implementations.{IMPL_DIRS[fw]}.idiomatic.workflow"


def impl_target(scenario: str, fw: str, func: str = "run") -> str:
    return f"{impl_module(scenario, fw)}:{func}"


def impl_path(scenario: str, fw: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / (impl_module(scenario, fw).replace(".", "/") + ".py")


def env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def workdir(scenario: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"poi-{scenario.lower()}-"))


class TrialError(RuntimeError):
    """The trial itself failed (LLM/API error, crash) — it produced no evidence."""
