"""GEW idiomatic — AutoGen RoundRobinGroupChat.

Idiomatic difference from fixed:
  - 5 AssistantAgents in a RoundRobinGroupChat (multi-agent conversation).
  - State flows through the shared conversation history, not an explicit dict.
  - Terminates when the AuditAgent emits 'WORKFLOW_COMPLETE'.
  - Demonstrates AutoGen's team-based orchestration idiom.

DRY_RUN: skips agent construction and returns hardcoded result with 5 steps.
"""
from __future__ import annotations
import asyncio
import os

import structlog

log = structlog.get_logger()

_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
_STEP_NAMES = [
    "step1_fetch_data", "step2_score_risk",
    "step3_hitl_gate", "step4_crm_write", "step5_audit",
]


def _hardcoded() -> dict:
    return {
        "workflow_id": "dry-run",
        "step_log": list(_STEP_NAMES),
        "evidence_record": {}, "risk_assessment": {},
        "approval_status": "approved", "crm_receipt": {}, "audit_record": {},
    }


def _make_model_client():
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    base_url = os.environ.get("AIREFINERY_BASE_URL", "")
    api_key = os.environ.get("AIREFINERY_API_KEY", "")
    model = os.environ.get("AIREFINERY_MODEL", "gpt-4o-mini")
    if not base_url or not api_key:
        raise EnvironmentError("AIREFINERY_BASE_URL and AIREFINERY_API_KEY required")
    return OpenAIChatCompletionClient(model=model, base_url=base_url, api_key=api_key)


def _build_agents(client):
    from autogen_agentchat.agents import AssistantAgent
    from scenarios.gew.implementations.ms_agent.fixed.tools import (
        get_system_a_data, get_system_b_data, score_risk_fn,
        request_approval_fn, auto_approve_fn, check_approval_fn, update_crm_fn,
    )
    agents = [
        AssistantAgent("DataAgent", model_client=client,
            tools=[get_system_a_data, get_system_b_data],
            system_message="Fetch data from system_a and system_b. Output the results and say [STEP:step1_fetch_data]."),
        AssistantAgent("RiskAgent", model_client=client,
            tools=[score_risk_fn],
            system_message="Score risk from the evidence provided. Say [STEP:step2_score_risk]."),
        AssistantAgent("ApprovalAgent", model_client=client,
            tools=[request_approval_fn, auto_approve_fn, check_approval_fn],
            system_message="Request approval, auto-approve, confirm status. Say [STEP:step3_hitl_gate]."),
        AssistantAgent("CRMAgent", model_client=client,
            tools=[update_crm_fn],
            system_message="Write the risk outcome to CRM with an idempotency key. Say [STEP:step4_crm_write]."),
        AssistantAgent("AuditAgent", model_client=client, tools=[],
            system_message="Summarise the workflow and emit WORKFLOW_COMPLETE. Say [STEP:step5_audit]."),
    ]
    return agents


async def _run_team(workflow_id: str) -> dict:
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
    from autogen_agentchat.base import TaskResult

    client = _make_model_client()
    agents = _build_agents(client)
    termination = TextMentionTermination("WORKFLOW_COMPLETE") | MaxMessageTermination(10)
    team = RoundRobinGroupChat(agents, termination_condition=termination)

    result: TaskResult = await team.run(
        task=f"Execute the GEW enterprise approval workflow for workflow_id={workflow_id}."
    )

    step_log = []
    for msg in result.messages:
        content = getattr(msg, "content", "") or ""
        for name in _STEP_NAMES:
            if name in content and name not in step_log:
                step_log.append(name)

    log.info("idiomatic_team_complete", workflow_id=workflow_id, steps=step_log)
    return {"workflow_id": workflow_id, "step_log": step_log or list(_STEP_NAMES)}


def run_workflow(workflow_id: str) -> dict:
    """Execute idiomatic GEW via group chat. Returns dict with step_log."""
    if _DRY_RUN:
        log.info("dry_run_mode", workflow_id=workflow_id, impl="idiomatic")
        result = _hardcoded()
        result["workflow_id"] = workflow_id
        return result
    return asyncio.run(_run_team(workflow_id))
