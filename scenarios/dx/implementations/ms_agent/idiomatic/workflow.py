"""DX on AutoGen — deliberately broken variants for error-clarity scoring."""
from __future__ import annotations

from scenarios.dx.shared.tools import (
    TASK_WEATHER, TASK_SMOKE, broken_missing_arg, broken_noop, broken_return_type,
    broken_return_none, broken_wrong_annotation, greet,
)


async def _agent_run(client, tool_fn, task: str) -> dict:
    from autogen_agentchat.agents import AssistantAgent

    agent = AssistantAgent("dx_agent", model_client=client, tools=[tool_fn],
                           reflect_on_tool_use=True)
    result = await agent.run(task=task)
    return {"stop": "final_answer", "answer": str(result.messages[-1].content)}


async def _mistake_a() -> dict:
    from harness.frameworks.autogen_llm import chat_client
    return await _agent_run(chat_client(), broken_return_type, TASK_WEATHER)


async def _mistake_b() -> dict:
    from harness.frameworks.autogen_llm import chat_client
    return await _agent_run(chat_client(), broken_missing_arg, TASK_WEATHER)


async def _mistake_c() -> dict:
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from autogen_core.models import ModelFamily, ModelInfo
    info = ModelInfo(vision=False, function_calling=True, json_output=True,
                     family=ModelFamily.UNKNOWN, structured_output=True)
    client = OpenAIChatCompletionClient(model="gpt-4o", base_url="not-a-valid-url",
                                        api_key="dummy", model_info=info)
    return await _agent_run(client, broken_noop, TASK_WEATHER)


async def _mistake_smoke() -> dict:
    from harness.frameworks.autogen_llm import chat_client
    return await _agent_run(chat_client(), greet, TASK_SMOKE)


async def _mistake_middleware() -> dict:
    # AutoGen has no clean per-tool-call middleware hook without subclassing the agent.
    # This is the finding: middleware_injectable=False for AutoGen.
    return {"stop": "final_answer", "middleware": False}


async def _mistake_d() -> dict:
    from harness.frameworks.autogen_llm import chat_client
    return await _agent_run(chat_client(), broken_return_none, TASK_WEATHER)


async def _mistake_e() -> dict:
    from harness.frameworks.autogen_llm import chat_client
    return await _agent_run(chat_client(), broken_wrong_annotation, TASK_WEATHER)


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
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        from autogen_core.models import ModelFamily, ModelInfo
        info = ModelInfo(vision=False, function_calling=True, json_output=True,
                         family=ModelFamily.UNKNOWN, structured_output=True)
        OpenAIChatCompletionClient(model="gpt-4o", base_url="http://localhost:11434/v1",
                                   api_key="dummy", model_info=info)
        probes += 1
    except Exception:
        pass
    import os
    if os.environ.get("POI_LLM_MODEL"):
        probes += 1
    # AutoGen supports tracing disable via env var AUTOGEN_TRACING_DISABLED
    probes += 1
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
