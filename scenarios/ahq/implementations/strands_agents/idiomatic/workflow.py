"""AHQ on Strands: tool_context.interrupt() gate, FileSessionManager persistence.

Strands ships file and S3 session managers but no database-backed one, so the
durable store here is the local file system (single-node only).
"""
from __future__ import annotations
from pathlib import Path

from strands import ToolContext  # module scope: Strands resolves the tool's type hints here

from harness.frameworks.strands_llm import model
from scenarios.ahq.shared.tools import (AGENT_NAME, INSTRUCTIONS, TASK, apply_plan_change, digest,
                                        lookup_account)

CUSTOM_STORE = False
BACKEND = "file (FileSessionManager)"


def _agent(run_id: str, workdir: str):
    from strands import Agent, tool
    from strands.session.file_session_manager import FileSessionManager

    @tool(name="apply_plan_change", description=apply_plan_change.__doc__, context=True)
    def gated(customer_id: str, new_plan: str, tool_context: ToolContext) -> str:
        decision = tool_context.interrupt("plan_change_approval",
                                          reason={"customer_id": customer_id, "new_plan": new_plan})
        if not decision.get("approved"):
            return "Plan change rejected by the approver."
        return apply_plan_change(customer_id, new_plan)

    sessions = FileSessionManager(session_id=run_id, storage_dir=str(Path(workdir) / "strands"))
    return Agent(agent_id=AGENT_NAME, name=AGENT_NAME, model=model(), system_prompt=INSTRUCTIONS,
                 tools=[tool(lookup_account), gated], session_manager=sessions, callback_handler=None)


def start(*, run_id: str, workdir: str, **_) -> dict:
    result = _agent(run_id, workdir)(TASK)
    if result.stop_reason != "interrupt" or not result.interrupts:
        return {"stop": "no_pause"}
    pending = result.interrupts[0]
    return {"hold": True, "paused": True, "backend": BACKEND, "resume_token": pending.id,
            "pending_digest": digest(pending.reason or {})}


def resume(*, run_id: str, workdir: str, approved: bool, resume_token: str, **_) -> dict:
    _agent(run_id, workdir)([{"interruptResponse": {"interruptId": resume_token,
                                                    "response": {"approved": approved}}}])
    return {"stop": "final_answer"}
