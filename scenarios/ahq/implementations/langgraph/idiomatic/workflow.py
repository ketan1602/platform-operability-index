"""AHQ on LangGraph: interrupt() inside the gated tool, PostgresSaver checkpoints."""
from __future__ import annotations
import os

from harness.frameworks.langgraph_llm import chat_model
from scenarios.ahq.shared.tools import (AGENT_NAME, INSTRUCTIONS, TASK, apply_plan_change, digest,
                                        lookup_account)

CUSTOM_STORE = False
BACKEND = "postgres (PostgresSaver)"


def _agent(checkpointer):
    from langchain_core.tools import StructuredTool, tool
    from langgraph.prebuilt import create_react_agent
    from langgraph.types import interrupt

    def gated(customer_id: str, new_plan: str) -> str:
        decision = interrupt({"customer_id": customer_id, "new_plan": new_plan})
        if not decision.get("approved"):
            return "Plan change rejected by the approver."
        return apply_plan_change(customer_id, new_plan)

    apply_tool = StructuredTool.from_function(gated, name="apply_plan_change",
                                              description=apply_plan_change.__doc__)
    return create_react_agent(chat_model(), [tool(lookup_account), apply_tool],
                              prompt=INSTRUCTIONS, checkpointer=checkpointer, name=AGENT_NAME)


def start(*, run_id: str, **_) -> dict:
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(os.environ["POSTGRES_URL"]) as saver:
        saver.setup()
        out = _agent(saver).invoke({"messages": [("user", TASK)]},
                                   {"configurable": {"thread_id": run_id}})
    if not out.get("__interrupt__"):
        return {"stop": "no_pause"}
    return {"hold": True, "paused": True, "backend": BACKEND,
            "pending_digest": digest(out["__interrupt__"][0].value)}


def resume(*, run_id: str, approved: bool, **_) -> dict:
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.types import Command

    with PostgresSaver.from_conn_string(os.environ["POSTGRES_URL"]) as saver:
        _agent(saver).invoke(Command(resume={"approved": approved}),
                             {"configurable": {"thread_id": run_id}})
    return {"stop": "final_answer"}
