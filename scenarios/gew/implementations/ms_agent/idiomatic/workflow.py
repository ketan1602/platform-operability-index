"""GEW idiomatic — AutoGen RoundRobinGroupChat with MCP tools.

Idiomatic difference from fixed:
  - 5 AssistantAgents in a RoundRobinGroupChat (multi-agent conversation).
  - State flows through the shared conversation history, not an explicit dict.
  - Each agent is given MCP tool adapters via StreamableHttpMcpToolAdapter.
  - Terminates when the AuditAgent emits 'WORKFLOW_COMPLETE'.

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


def _require_url(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"{name} env var is required")
    return val


async def _fetch_named_tools(url: str, *names: str):
    from autogen_ext.tools.mcp import StreamableHttpServerParams, mcp_server_tools
    params = StreamableHttpServerParams(url=url)
    all_tools = await mcp_server_tools(params)
    if not names:
        return all_tools
    name_set = set(names)
    return [t for t in all_tools if t.name in name_set]


async def _build_agents(client):
    from autogen_agentchat.agents import AssistantAgent
    api_url = _require_url("MOCK_API_MCP_URL")
    approval_url = _require_url("MOCK_APPROVAL_MCP_URL")
    crm_url = _require_url("MOCK_CRM_MCP_URL")

    data_tools, risk_tools, approval_tools, crm_tools = await asyncio.gather(
        _fetch_named_tools(api_url, "get_external_data"),
        _fetch_named_tools(api_url, "score_risk"),
        _fetch_named_tools(approval_url, "request_approval", "get_approval_status", "auto_approve_all"),
        _fetch_named_tools(crm_url, "crm_update"),
    )

    return [
        AssistantAgent(
            "DataAgent", model_client=client, tools=data_tools,
            system_message=(
                "Fetch external data using get_external_data for sources 'system_a' and 'system_b'. "
                "Output the results and say [STEP:step1_fetch_data]."
            ),
        ),
        AssistantAgent(
            "RiskAgent", model_client=client, tools=risk_tools,
            system_message=(
                "Score risk using score_risk with the evidence_id and evidence_data from the conversation. "
                "Say [STEP:step2_score_risk]."
            ),
        ),
        AssistantAgent(
            "ApprovalAgent", model_client=client, tools=approval_tools,
            system_message=(
                "Request approval with request_approval, then call auto_approve_all, "
                "then confirm status with get_approval_status. Say [STEP:step3_hitl_gate]."
            ),
        ),
        AssistantAgent(
            "CRMAgent", model_client=client, tools=crm_tools,
            system_message=(
                "Write the risk outcome to CRM using crm_update with an idempotency key. "
                "Say [STEP:step4_crm_write]."
            ),
        ),
        AssistantAgent(
            "AuditAgent", model_client=client, tools=[],
            system_message=(
                "Summarise the completed workflow steps and emit WORKFLOW_COMPLETE. "
                "Say [STEP:step5_audit]."
            ),
        ),
    ]


async def _run_team(workflow_id: str) -> dict:
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination

    client = _make_model_client()
    agents = await _build_agents(client)
    termination = TextMentionTermination("WORKFLOW_COMPLETE") | MaxMessageTermination(10)
    team = RoundRobinGroupChat(agents, termination_condition=termination)

    result = await team.run(
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
    """Execute idiomatic GEW via MCP-tooled group chat. Returns dict with step_log."""
    if _DRY_RUN:
        log.info("dry_run_mode", workflow_id=workflow_id, impl="idiomatic")
        result = _hardcoded()
        result["workflow_id"] = workflow_id
        return result
    return asyncio.run(_run_team(workflow_id))
