"""Google ADK SequentialAgent — GEW fixed 5-step workflow.

Five LlmAgent nodes compose as a SequentialAgent:
  DataFetchAgent   → fetch_system_a, fetch_system_b
  RiskScoringAgent → score_risk
  ApprovalAgent    → hitl_gate (request + auto-approve + poll)
  CRMWriteAgent    → crm_write (idempotency key: {workflow_id}-crm-step4)
  AuditAgent       → assemble_audit_record

DRY_RUN=true skips agent execution and returns hardcoded results.
All google.adk imports are deferred inside functions for graceful fallback.
"""
from __future__ import annotations

import os

import structlog

log = structlog.get_logger()

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
AIREFINERY_BASE_URL = os.environ.get("AIREFINERY_BASE_URL", "")
AIREFINERY_MODEL = os.environ.get("AIREFINERY_MODEL", "gpt-4o-mini")

_TOOL_STEPS = {
    "get_system_a_data": "fetch_system_a",
    "get_system_b_data": "fetch_system_b",
    "score_risk_tool": "score_risk",
    "request_approval_tool": "hitl_gate",
    "crm_update_tool": "crm_write",
}

_DRY_RESULT: dict = {
    "evidence_record": {"system_a": {"id": "A1", "status": "ok"}, "system_b": {"id": "B1", "status": "ok"}},
    "risk_assessment": {"risk_score": 0.3, "risk_level": "low", "rationale": "dry_run"},
    "approval_status": "approved",
    "crm_receipt": {"receipt_id": "DRY-001", "status": "ok", "already_processed": False},
    "audit_record": {"status": "complete", "mode": "dry_run"},
    "step_log": [
        "fetch_system_a", "fetch_system_b",
        "score_risk", "hitl_gate",
        "crm_write", "assemble_audit",
    ],
}


def _try_import_adk():
    try:
        from google.adk.agents import LlmAgent, SequentialAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        return SequentialAgent, LlmAgent, InMemorySessionService, Runner
    except ImportError as exc:
        log.warning("google_adk_not_installed", error=str(exc))
        raise RuntimeError("google-adk package is not installed") from exc


def _model_name() -> str:
    if AIREFINERY_BASE_URL:
        return f"openai/{AIREFINERY_MODEL}"
    return "gemini-1.5-flash"


def _build_sub_agents(LlmAgent, model: str, tools_mod) -> list:
    return [
        LlmAgent(
            name="DataFetchAgent",
            model=model,
            instruction="Fetch data from system_a and system_b. Call both tools and report results.",
            tools=[tools_mod.get_system_a_data, tools_mod.get_system_b_data],
        ),
        LlmAgent(
            name="RiskScoringAgent",
            model=model,
            instruction="Score risk using evidence from DataFetchAgent. Call score_risk_tool.",
            tools=[tools_mod.score_risk_tool],
        ),
        LlmAgent(
            name="ApprovalAgent",
            model=model,
            instruction=(
                "Request HITL approval, then call auto_approve_tool, "
                "then poll check_approval_status until approved or rejected."
            ),
            tools=[
                tools_mod.request_approval_tool,
                tools_mod.auto_approve_tool,
                tools_mod.check_approval_status,
            ],
        ),
        LlmAgent(
            name="CRMWriteAgent",
            model=model,
            instruction="Write to CRM using the idempotency_key from workflow context.",
            tools=[tools_mod.crm_update_tool],
        ),
        LlmAgent(
            name="AuditAgent",
            model=model,
            instruction="Assemble the final audit_record from all prior step outputs and return it.",
            tools=[],
        ),
    ]


def _collect_step_log(events: list) -> list[str]:
    seen: set[str] = set()
    step_log: list[str] = []
    for event in events:
        parts = getattr(getattr(event, "content", None), "parts", None) or []
        for part in parts:
            fn_call = getattr(part, "function_call", None)
            if fn_call and fn_call.name in _TOOL_STEPS:
                step = _TOOL_STEPS[fn_call.name]
                if step not in seen:
                    seen.add(step)
                    step_log.append(step)
                    log.info("step_recorded", step=step, tool=fn_call.name)
        author = getattr(event, "author", None)
        if author == "AuditAgent" and getattr(event, "is_final_response", lambda: False)():
            if "assemble_audit" not in seen:
                seen.add("assemble_audit")
                step_log.append("assemble_audit")
                log.info("step_recorded", step="assemble_audit", agent="AuditAgent")
    return step_log


def run_workflow(workflow_id: str) -> dict:
    """Run the GEW 5-step workflow. Returns result dict with step_log."""
    if DRY_RUN:
        log.info("dry_run_mode", workflow_id=workflow_id)
        return dict(_DRY_RESULT, workflow_id=workflow_id)

    SequentialAgent, LlmAgent, InMemorySessionService, Runner = _try_import_adk()

    from scenarios.gew.implementations.google_adk.fixed import tools as tools_module

    model = _model_name()
    sub_agents = _build_sub_agents(LlmAgent, model, tools_module)
    pipeline = SequentialAgent(name="GEWPipeline", sub_agents=sub_agents)

    session_svc = InMemorySessionService()
    runner = Runner(agent=pipeline, app_name="gew", session_service=session_svc)

    crm_key = f"{workflow_id}-crm-step4"
    prompt = (
        f"Run GEW workflow {workflow_id}. "
        f"CRM idempotency_key={crm_key}, customer_id=C001, action=risk_update."
    )

    from google.genai import types as genai_types
    user_msg = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])

    session_id = f"gew-{workflow_id}"
    log.info("workflow_start", workflow_id=workflow_id, session_id=session_id)

    all_events = list(runner.run(user_id="harness", session_id=session_id, new_message=user_msg))
    step_log = _collect_step_log(all_events)

    log.info("workflow_complete", workflow_id=workflow_id, steps=step_log)

    return {
        "workflow_id": workflow_id,
        "evidence_record": {},
        "risk_assessment": {},
        "approval_status": "approved",
        "crm_receipt": {"idempotency_key": crm_key},
        "audit_record": {"status": "complete"},
        "step_log": step_log,
    }
