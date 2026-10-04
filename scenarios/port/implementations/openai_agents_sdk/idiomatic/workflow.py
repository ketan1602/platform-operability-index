"""PORT on OpenAI Agents SDK: sub_test='switch' (P6 switching cost) and 'isolation' (P2/SMA)."""
from __future__ import annotations
import json

from harness.frameworks.openai_agents_llm import model
from scenarios.port.shared.tools import (
    TASK, TASK_FETCH_TPL, analyse, draft_report, fetch_data, search,
)


def _json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


async def _run_switch() -> dict:
    from agents import Agent, Runner, function_tool

    tools = [function_tool(search), function_tool(analyse), function_tool(draft_report)]
    agent = Agent(name="port_agent", model=model(), tools=tools)
    result = await Runner.run(agent, TASK)
    return {"stop": "final_answer", "sub_test": "switch",
            "answer": str(result.final_output),
            "state_json_safe": _json_safe(result)}


async def _run_tools_raw() -> dict:
    from agents import Agent, Runner

    try:
        agent = Agent(name="port_raw", model=model(), tools=[search, analyse, draft_report])
        result = await Runner.run(agent, TASK)
        answer = str(result.final_output)
    except Exception:
        answer = ""
    return {"stop": "final_answer", "sub_test": "tools_raw", "answer": answer}


async def _run_isolation(run_id: str) -> dict:
    from agents import Agent, Runner, function_tool

    agent = Agent(name="port_agent", model=model(), tools=[function_tool(fetch_data)])
    task = TASK_FETCH_TPL.format(run_id=run_id)
    result = await Runner.run(agent, task)
    return {"stop": "final_answer", "sub_test": "isolation", "run_id": run_id,
            "answer": str(result.final_output)}


async def _run_context_port() -> dict:
    from agents import Agent, Runner, function_tool
    from scenarios.port.shared.history import CONTEXT_KEYWORD, FOLLOWUP, HISTORY

    # SDK requires content to be str (not None) when tool_calls present
    history = [{k: v for k, v in m.items() if not (k == "content" and v is None)}
               for m in HISTORY]
    agent = Agent(name="port_agent", model=model(),
                  instructions="You are a helpful assistant.",
                  tools=[function_tool(search)])
    full_input = history + [{"role": "user", "content": FOLLOWUP}]
    try:
        result = await Runner.run(agent, full_input)
        answer = str(result.final_output)
        portable = CONTEXT_KEYWORD in answer
    except Exception:
        # Multi-turn history injection unsupported by the backing model API
        answer = ""
        portable = False
    return {"stop": "final_answer", "sub_test": "context_port",
            "context_portable": portable,
            "injection": "native", "answer": answer}


async def run(*, sub_test: str = "switch", run_id: str = "", **_) -> dict:
    if sub_test == "tools_raw":
        return await _run_tools_raw()
    if sub_test == "isolation":
        return await _run_isolation(run_id)
    if sub_test == "context_port":
        return await _run_context_port()
    return await _run_switch()
