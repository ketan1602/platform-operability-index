"""DX on Google ADK — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, broken_missing_arg, broken_noop, broken_return_type,
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


_DISPATCH = {"A": _mistake_a, "B": _mistake_b, "C": _mistake_c}


async def run(*, mistake: str = "A", **_) -> dict:
    fn = _DISPATCH.get(mistake)
    if fn is None:
        return {"stop": "error", "error": f"unknown mistake={mistake!r}"}
    return await fn()
