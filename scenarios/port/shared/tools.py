"""PORT — shared tools for portability sub-tests.

get_weather: used in sub-test 3 (tool extensibility) — added dynamically at run time.
fetch_data:  used in sub-test 2 (process isolation) — each trial records its own run_id.
"""
from __future__ import annotations

from harness.shared import ledger

AGENT_NAME = "port_agent"
TOOL_EVENT_WEATHER = "get_weather"
TOOL_EVENT_FETCH = "fetch_data"
TASK_WEATHER = "What is the weather in London?"
TASK_FETCH_TPL = "Call fetch_data with run_id='{run_id}'."


def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    ledger.record(TOOL_EVENT_WEATHER, city=city)
    return f"The weather in {city} is 72°F and sunny."


def fetch_data(run_id: str) -> str:
    """Fetch data for the given run ID."""
    ledger.record(TOOL_EVENT_FETCH, run_id=run_id)
    return f"Data fetched for run_id={run_id}"
