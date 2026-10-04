"""DX on Strands — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, TASK_SMOKE, broken_missing_arg, broken_noop, broken_return_type,
    broken_return_none, broken_wrong_annotation, greet,
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


def _mistake_smoke() -> dict:
    from harness.frameworks.strands_llm import model
    return _run_agent(model(), greet, TASK_SMOKE)


def _mistake_middleware() -> dict:
    from strands import Agent, tool
    from harness.frameworks.strands_llm import model
    from harness.shared import ledger

    def _handler(event_loop_metrics=None, **kwargs):
        if kwargs.get("event_loop_cycle_type") == "tool":
            ledger.record("middleware_fired")

    agent = Agent(name="dx_agent", model=model(), tools=[tool(broken_noop)],
                  callback_handler=_handler)
    agent(TASK_WEATHER)
    return {"stop": "final_answer", "middleware": True}


def _mistake_d() -> dict:
    from harness.frameworks.strands_llm import model
    return _run_agent(model(), broken_return_none, TASK_WEATHER)


def _mistake_e() -> dict:
    from harness.frameworks.strands_llm import model
    return _run_agent(model(), broken_wrong_annotation, TASK_WEATHER)


def _mistake_hitl() -> dict:
    from harness.shared import ledger
    import os, time
    # poi:custom-begin
    approval = os.environ.get("POI_HITL_APPROVAL", "")
    ledger.record("hitl_hold")
    deadline = time.time() + 60
    while time.time() < deadline:
        if approval and os.path.exists(approval):
            ledger.record("hitl_completed")
            return {"stop": "final_answer", "answer": "Weather: 72F"}
        time.sleep(0.5)
    return {"stop": "final_answer", "answer": "timeout"}
    # poi:custom-end


def _escape_hatch() -> dict:
    probes = 0
    try:
        from strands.models.openai import OpenAIModel
        OpenAIModel(client_args={"base_url": "http://localhost:11434/v1", "api_key": "dummy"},
                    model_id="gpt-4o")
        probes += 1
    except Exception:
        pass
    import os
    if os.environ.get("POI_LLM_MODEL"):
        probes += 1
    # Strands: callback_handler=None disables all event callbacks including tracing
    probes += 1
    return {"stop": "final_answer", "probes_passed": probes}


_DISPATCH = {
    "A": _mistake_a, "B": _mistake_b, "C": _mistake_c,
    "D": _mistake_d, "E": _mistake_e,
    "SMOKE": _mistake_smoke, "MIDDLEWARE": _mistake_middleware,
    "ESCAPE_HATCH": _escape_hatch, "HITL": _mistake_hitl,
}


def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return fn()
