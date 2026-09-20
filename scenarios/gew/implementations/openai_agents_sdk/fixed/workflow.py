"""GEW — OpenAI Agents SDK fixed implementation.

5 sequential agents, each owning one workflow step.
State passes between agents via the task prompt string.
DRY_RUN=true skips Runner.run() and returns hardcoded outputs.
"""
from __future__ import annotations
import asyncio
import json
import os

import structlog

log = structlog.get_logger()

_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
_STEP_NAMES = ["step1_data", "step2_risk", "step3_hitl", "step4_crm", "step5_audit"]


def _hardcoded_result(workflow_id: str) -> dict:
    return {
        "workflow_id": workflow_id,
        "evidence_record": {"system_a": "mock-a", "system_b": "mock-b"},
        "risk_assessment": {"risk_score": 0.2, "risk_level": "low"},
        "approval_status": "approved",
        "crm_receipt": {"receipt_id": "dry-run", "status": "ok"},
        "audit_record": {"workflow_id": workflow_id, "complete": True},
        "step_log": list(_STEP_NAMES),
    }


def _make_client():
    base_url = os.environ.get("AIREFINERY_BASE_URL")
    api_key = os.environ.get("AIREFINERY_API_KEY")
    if not base_url or not api_key:
        return None
    from openai import AsyncOpenAI
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


def _safe_parse(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def _run_agent(agent, prompt: str) -> str:
    from agents import Runner
    result = await Runner.run(agent, prompt)
    return result.final_output


async def _step1(workflow_id: str) -> str:
    from agents import Agent
    from scenarios.gew.implementations.openai_agents_sdk.fixed import tools
    agent = Agent(
        name="DataFetcher",
        instructions="Fetch data from both system_a and system_b. Return a JSON object with both.",
        tools=[tools.get_system_a_data, tools.get_system_b_data],
    )
    return await _run_agent(agent, f"Fetch all external data for workflow {workflow_id}.")


async def _step2(evidence_raw: str) -> str:
    from agents import Agent
    from scenarios.gew.implementations.openai_agents_sdk.fixed import tools
    agent = Agent(
        name="RiskScorer",
        instructions="Score risk from the provided evidence using score_risk_tool.",
        tools=[tools.score_risk_tool],
    )
    return await _run_agent(agent, f"Score risk for evidence: {evidence_raw}")


async def _step3(workflow_id: str, risk_raw: str) -> str:
    from agents import Agent
    from scenarios.gew.implementations.openai_agents_sdk.fixed import tools
    agent = Agent(
        name="HITLGate",
        instructions=(
            "Request human approval, then immediately call auto_approve_tool "
            "to approve it (test mode), then verify with check_approval_status_tool."
        ),
        tools=[
            tools.request_approval_tool,
            tools.auto_approve_tool,
            tools.check_approval_status_tool,
        ],
    )
    return await _run_agent(
        agent,
        f"Request and approve HITL gate for workflow {workflow_id}. Risk: {risk_raw}",
    )


async def _step4(workflow_id: str, evidence_raw: str) -> str:
    from agents import Agent
    from scenarios.gew.implementations.openai_agents_sdk.fixed import tools
    idempotency_key = f"{workflow_id}-crm-step4"
    agent = Agent(
        name="CRMWriter",
        instructions="Write evidence to CRM using the exact idempotency_key provided.",
        tools=[tools.crm_update_tool],
    )
    return await _run_agent(
        agent,
        f"Update CRM. idempotency_key={idempotency_key} evidence={evidence_raw}",
    )


async def _async_workflow(workflow_id: str) -> dict:
    client = _make_client()
    if client:
        from agents import set_default_openai_client
        set_default_openai_client(client)

    step_log: list[str] = []

    evidence_raw = await _step1(workflow_id)
    step_log.append("step1_data")
    log.info("step_complete", step="step1_data", workflow_id=workflow_id)

    risk_raw = await _step2(evidence_raw)
    step_log.append("step2_risk")
    log.info("step_complete", step="step2_risk", workflow_id=workflow_id)

    approval_raw = await _step3(workflow_id, risk_raw)
    step_log.append("step3_hitl")
    log.info("step_complete", step="step3_hitl", workflow_id=workflow_id)

    crm_raw = await _step4(workflow_id, evidence_raw)
    step_log.append("step4_crm")
    log.info("step_complete", step="step4_crm", workflow_id=workflow_id)

    audit_record = {
        "workflow_id": workflow_id,
        "evidence": _safe_parse(evidence_raw),
        "risk": _safe_parse(risk_raw),
        "approval": _safe_parse(approval_raw),
        "crm": _safe_parse(crm_raw),
        "complete": True,
    }
    step_log.append("step5_audit")
    log.info("step_complete", step="step5_audit", workflow_id=workflow_id)

    return {
        "workflow_id": workflow_id,
        "evidence_record": _safe_parse(evidence_raw),
        "risk_assessment": _safe_parse(risk_raw),
        "approval_status": _safe_parse(approval_raw),
        "crm_receipt": _safe_parse(crm_raw),
        "audit_record": audit_record,
        "step_log": step_log,
    }


def run_workflow(workflow_id: str) -> dict:
    """Run the GEW workflow. Uses asyncio.run() for the async agent loop."""
    if _DRY_RUN:
        log.info("dry_run_mode", workflow_id=workflow_id)
        return _hardcoded_result(workflow_id)
    return asyncio.run(_async_workflow(workflow_id))
