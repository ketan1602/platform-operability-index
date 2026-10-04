"""DX on Google ADK — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, TASK_SMOKE, broken_missing_arg, broken_noop, broken_return_type,
    broken_return_none, broken_wrong_annotation, greet,
)


async def _run_agent(model, tool_fn, task: str) -> dict:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from harness.frameworks.adk_llm import run_to_end, user_text

    agent = LlmAgent(name="dx_agent", model=model, tools=[tool_fn])
    runner = InMemoryRunner(agent=agent, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    events = await run_to_end(runner, session.id, user_text(task))
    final = [e for e in events if e.is_final_response() and e.content and e.content.parts]
    answer = final[-1].content.parts[0].text if final else ""
    return {"stop": "final_answer", "answer": answer}


async def _mistake_a() -> dict:
    from harness.frameworks.adk_llm import llm
    return await _run_agent(llm(), broken_return_type, TASK_WEATHER)


async def _mistake_b() -> dict:
    from harness.frameworks.adk_llm import llm
    return await _run_agent(llm(), broken_missing_arg, TASK_WEATHER)


async def _mistake_c() -> dict:
    from google.adk.models.lite_llm import LiteLlm
    from harness.shared.llm import get_model
    mdl = LiteLlm(model=f"openai/{get_model()}", api_base="not-a-valid-url",
                  api_key="dummy", num_retries=0)
    return await _run_agent(mdl, broken_noop, TASK_WEATHER)


async def _mistake_smoke() -> dict:
    from harness.frameworks.adk_llm import llm
    return await _run_agent(llm(), greet, TASK_SMOKE)


async def _mistake_middleware() -> dict:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from harness.frameworks.adk_llm import llm, run_to_end, user_text
    from harness.shared import ledger

    def _after_tool(callback_context, tool_response):
        ledger.record("middleware_fired")
        return tool_response

    agent = LlmAgent(name="dx_agent", model=llm(), tools=[broken_noop],
                     after_tool_callback=_after_tool)
    runner = InMemoryRunner(agent=agent, app_name="poi")
    session = await runner.session_service.create_session(app_name="poi", user_id="poi")
    await run_to_end(runner, session.id, user_text(TASK_WEATHER))
    return {"stop": "final_answer", "middleware": True}


async def _mistake_d() -> dict:
    from harness.frameworks.adk_llm import llm
    return await _run_agent(llm(), broken_return_none, TASK_WEATHER)


async def _mistake_e() -> dict:
    from harness.frameworks.adk_llm import llm
    return await _run_agent(llm(), broken_wrong_annotation, TASK_WEATHER)


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
        from google.adk.models.lite_llm import LiteLlm
        LiteLlm(model="openai/gpt-4o", api_base="http://localhost:11434/v1",
                api_key="dummy", num_retries=0)
        probes += 1
    except Exception:
        pass
    import os
    if os.environ.get("POI_LLM_MODEL"):
        probes += 1
    # ADK does not support disabling its built-in tracing without monkeypatching
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
