"""DX on OpenAI Agents SDK — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, TASK_SMOKE, broken_missing_arg, broken_noop, broken_return_type,
    broken_return_none, broken_wrong_annotation, greet,
)


async def _run_agent(model, tool_fn, task: str) -> dict:
    from agents import Agent, Runner, function_tool

    agent = Agent(name="dx_agent", model=model, tools=[function_tool(tool_fn)])
    result = await Runner.run(agent, task)
    return {"stop": "final_answer", "answer": str(result.final_output)}


async def _mistake_a() -> dict:
    from harness.frameworks.openai_agents_llm import model
    return await _run_agent(model(), broken_return_type, TASK_WEATHER)


async def _mistake_b() -> dict:
    from harness.frameworks.openai_agents_llm import model
    return await _run_agent(model(), broken_missing_arg, TASK_WEATHER)


async def _mistake_c() -> dict:
    from agents import OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI
    set_tracing_disabled(True)
    client = AsyncOpenAI(base_url="not-a-valid-url", api_key="dummy")
    from harness.shared.llm import get_model
    mdl = OpenAIChatCompletionsModel(model=get_model(), openai_client=client)
    return await _run_agent(mdl, broken_noop, TASK_WEATHER)


async def _mistake_smoke() -> dict:
    from harness.frameworks.openai_agents_llm import model
    return await _run_agent(model(), greet, TASK_SMOKE)


async def _mistake_middleware() -> dict:
    from agents import Agent, Runner, function_tool
    from agents.tracing import TracingProcessor
    from harness.frameworks.openai_agents_llm import model
    from harness.shared import ledger

    class _MWProcessor(TracingProcessor):
        def on_trace_start(self, trace): pass
        def on_trace_end(self, trace): pass
        def on_span_start(self, span): pass
        def on_span_end(self, span):
            if getattr(getattr(span, "span_data", None), "type", None) == "tool":
                ledger.record("middleware_fired")
        def shutdown(self): pass
        def force_flush(self): pass

    from agents import set_trace_processors
    set_trace_processors([_MWProcessor()])
    agent = Agent(name="dx_agent", model=model(), tools=[function_tool(broken_noop)])
    await Runner.run(agent, TASK_WEATHER)
    return {"stop": "final_answer", "middleware": True}


async def _mistake_d() -> dict:
    from harness.frameworks.openai_agents_llm import model
    return await _run_agent(model(), broken_return_none, TASK_WEATHER)


async def _mistake_e() -> dict:
    from harness.frameworks.openai_agents_llm import model
    return await _run_agent(model(), broken_wrong_annotation, TASK_WEATHER)


async def _mistake_hitl() -> dict:
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


async def _escape_hatch() -> dict:
    probes = 0
    try:
        from openai import AsyncOpenAI
        AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="dummy")
        probes += 1
    except Exception:
        pass
    import os
    if os.environ.get("POI_LLM_MODEL"):
        probes += 1
    try:
        from agents import set_tracing_disabled
        set_tracing_disabled(True)
        set_tracing_disabled(False)  # restore
        probes += 1
    except Exception:
        pass
    return {"stop": "final_answer", "probes_passed": probes}


_DISPATCH = {
    "A": _mistake_a, "B": _mistake_b, "C": _mistake_c,
    "D": _mistake_d, "E": _mistake_e,
    "SMOKE": _mistake_smoke, "MIDDLEWARE": _mistake_middleware,
    "ESCAPE_HATCH": _escape_hatch, "HITL": _mistake_hitl,
}


async def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return await fn()
