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
