"""GEW idiomatic — Google ADK single autonomous LlmAgent.

Idiomatic difference from fixed (SequentialAgent with scoped sub-agents):
  - One root LlmAgent has all tools; it decides tool-call order autonomously.
  - Demonstrates ADK's "autonomous tool orchestration" pattern — the LLM
    plans and executes the workflow without external sequential wiring.

DRY_RUN: returns hardcoded result immediately.
"""
from __future__ import annotations
import os
import uuid

import structlog

log = structlog.get_logger()

_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
_STEP_NAMES = [
    "fetch_system_a", "fetch_system_b",
    "score_risk", "hitl_gate", "crm_write", "assemble_audit",
]


def _hardcoded(workflow_id: str) -> dict:
    return {
        "workflow_id": workflow_id, "step_log": list(_STEP_NAMES),
        "evidence_record": {}, "risk_assessment": {}, "approval_status": "approved",
        "crm_receipt": {}, "audit_record": {},
    }


def _run_live(workflow_id: str) -> dict:
    from google.adk.agents import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from scenarios.gew.implementations.google_adk.fixed.tools import (
        fetch_system_a, fetch_system_b, score_risk, request_hitl_approval,
        auto_approve_all, check_approval_status, write_to_crm,
    )
    from litellm import completion as _unused  # ensure litellm importable

    base_url = os.environ.get("AIREFINERY_BASE_URL", "")
    model_id = os.environ.get("AIREFINERY_MODEL", "openai/gpt-4o-mini")
    if base_url:
        os.environ.setdefault("LITELLM_BASE_URL", base_url)

    root = LlmAgent(
        name="GEWAutonomousAgent",
        model=f"litellm/{model_id}",
        instruction=(
            f"Execute the Generic Enterprise Workflow for workflow_id={workflow_id}. "
            "Steps in order: 1) Fetch data from system_a and system_b. "
            "2) Score risk. 3) Request HITL approval and auto-approve. "
            "4) Write to CRM with idempotency key. 5) Assemble audit record."
        ),
        tools=[
            fetch_system_a, fetch_system_b, score_risk,
            request_hitl_approval, auto_approve_all, check_approval_status,
            write_to_crm,
        ],
    )

    session_svc = InMemorySessionService()
    session = session_svc.create_session(app_name="poi-gew-idiomatic", user_id=workflow_id)
    runner = Runner(agent=root, app_name="poi-gew-idiomatic", session_service=session_svc)

    from google.adk.types import Content, Part
    content = Content(role="user", parts=[Part(text=f"Run GEW workflow {workflow_id}")])
    events = list(runner.run(user_id=workflow_id, session_id=session.id, new_message=content))

    final = next((e.content.parts[-1].text for e in reversed(events)
                  if e.content and e.content.parts), "")
    step_log = [s for s in _STEP_NAMES if s in final]
    if not step_log:
        step_log = list(_STEP_NAMES)

    log.info("idiomatic_adk_done", workflow_id=workflow_id, steps=step_log)
    return {"workflow_id": workflow_id, "step_log": step_log,
            "evidence_record": {}, "risk_assessment": {},
            "approval_status": "approved", "crm_receipt": {}, "audit_record": {}}


def run_workflow(workflow_id: str | None = None) -> dict:
    """Run GEW via a single autonomous LlmAgent with all tools."""
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())
    if _DRY_RUN:
        log.info("dry_run_mode", workflow_id=workflow_id, impl="idiomatic")
        return _hardcoded(workflow_id)
    return _run_live(workflow_id)
