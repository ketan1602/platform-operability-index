"""DX on Strands — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, broken_missing_arg, broken_noop, broken_return_type,
)


def _run_agent(model, tool_fn, task: str) -> dict:
    from strands import Agent, tool

    agent = Agent(name="dx_agent", model=model, tools=[tool(tool_fn)], callback_handler=None)
    result = agent(task)
    return {"stop": "final_answer", "answer": str(result)}


def _mistake_a() -> dict:
    from harness.frameworks.strands_llm import model
    return _run_agent(model(), broken_return_type, TASK_WEATHER)


def _mistake_b() -> dict:
    from harness.frameworks.strands_llm import model
    return _run_agent(model(), broken_missing_arg, TASK_WEATHER)


def _mistake_c() -> dict:
    from strands.models.openai import OpenAIModel
    from harness.shared.llm import get_model
    mdl = OpenAIModel(client_args={"base_url": "not-a-valid-url", "api_key": "dummy"},
                      model_id=get_model())
    return _run_agent(mdl, broken_noop, TASK_WEATHER)


_DISPATCH = {"A": _mistake_a, "B": _mistake_b, "C": _mistake_c}


def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return fn()
