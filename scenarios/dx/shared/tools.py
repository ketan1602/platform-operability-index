"""DX — minimal tools for developer-experience error-clarity testing.

These are intentionally simple so the harness can focus on the *error messages*
produced by each framework, not on tool complexity.
"""
from __future__ import annotations


TASK_WEATHER = "What is the weather in London?"
TASK_GREET = "Say hello."


def get_weather(city: str) -> str:
    """Get the current weather for a city. Returns a plain-text description."""
    return f"The weather in {city} is 72°F and sunny."


def broken_return_type(city: str) -> str:
    """Intentionally returns int instead of declared str — Mistake A."""
    return 42  # type: ignore[return-value]


def broken_missing_arg() -> str:
    """Intentionally missing the required `city` argument — Mistake B."""
    return "London weather unknown"


def broken_noop(x: str) -> str:
    """Placeholder for Mistake C (LLM init error); the tool itself is fine."""
    return f"noop: {x}"


def broken_return_none(x: str) -> str:
    """Intentionally returns None instead of declared str — Mistake D."""
    return None  # type: ignore[return-value]


def broken_wrong_annotation(city: int) -> str:
    """Wrong type annotation: city declared int but callers pass str — Mistake E."""
    return f"weather for {city}"


TASK_SMOKE = "Use the greet tool to greet someone named 'poi-smoke-ok' and tell me what it said."


def greet(name: str) -> str:
    """Greet a user by name. Used for the smoke/functional-verification sub-test."""
    from harness.shared import ledger
    ledger.record("dx_smoke", name=name)
    return f"Hello, {name}!"
