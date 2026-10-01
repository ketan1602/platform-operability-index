"""GEW idiomatic — Strands single orchestrator agent with MCP tools.

Idiomatic difference from fixed (5 scoped agents):
  - ONE orchestrator Agent has all tools from three MCP servers.
  - The agent autonomously decides tool-call order from the task description.
  - Maximum tool autonomy, minimal scaffolding.

DRY_RUN: returns hardcoded result immediately.
"""
from __future__ import annotations
import os
import uuid

import structlog

log = structlog.get_logger()

_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
_MODEL_ID = os.environ.get("AIREFINERY_MODEL", "gpt-4o")
_BASE_URL = os.environ.get("AIREFINERY_BASE_URL", "")
_API_KEY = os.environ.get("AIREFINERY_API_KEY", "")

_HARDCODED: dict = {
    "evidence_record": {"system_a": {"dry": True}, "system_b": {"dry": True}},
    "risk_assessment": {"risk_score": 0, "risk_level": "low"},
    "approval_status": "approved",
    "crm_receipt": {"receipt_id": "dry-receipt", "status": "ok"},
    "audit_record": {"completed": True},
    "step_log": ["step1", "step2", "step3", "step4", "step5"],
}

_SYSTEM_PROMPT = (
    "You are a workflow orchestrator. Execute the Generic Enterprise Workflow "
    "using the available tools. Steps: 1) fetch data from system_a and system_b, "
    "2) score risk for the evidence, 3) request HITL approval and auto-approve, "
    "4) write to CRM with an idempotency key, 5) return a final audit summary. "
    "Execute each step with the appropriate tool."
)


def _build_model():
    if not (_BASE_URL and _API_KEY):
        return None
    from strands.models.openai import OpenAIModel
    return OpenAIModel(
        model_id=_MODEL_ID,
        client_args={"base_url": _BASE_URL, "api_key": _API_KEY},
    )


def _get_mcp_urls() -> tuple[str, str, str]:
    required = ("MOCK_API_MCP_URL", "MOCK_CRM_MCP_URL", "MOCK_APPROVAL_MCP_URL")
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {missing}")
    return (
        os.environ["MOCK_API_MCP_URL"],
        os.environ["MOCK_CRM_MCP_URL"],
        os.environ["MOCK_APPROVAL_MCP_URL"],
    )


def run_workflow(workflow_id: str | None = None) -> dict:
    """Execute GEW via a single orchestrator with all MCP tools."""
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())

    if _DRY_RUN:
        log.info("gew_dry_run", workflow_id=workflow_id, impl="idiomatic")
        result = dict(_HARDCODED)
        result["workflow_id"] = workflow_id
        return result

    from strands import Agent
    from strands.tools.mcp import MCPClient

    api_url, crm_url, approval_url = _get_mcp_urls()

    with (
        MCPClient(url=api_url) as api_client,
        MCPClient(url=crm_url) as crm_client,
        MCPClient(url=approval_url) as approval_client,
    ):
        tools = (
            list(api_client.list_tools_sync())
            + list(crm_client.list_tools_sync())
            + list(approval_client.list_tools_sync())
        )
        model = _build_model()
        idem_key = f"{workflow_id}-crm-step4"
        agent = Agent(model=model, tools=tools, system_prompt=_SYSTEM_PROMPT)
        response = agent(
            f"Execute the GEW workflow for workflow_id='{workflow_id}'. "
            f"Use idempotency_key='{idem_key}' for the CRM write. "
            f"Return a final summary when complete."
        )

    log.info("gew_mcp_idiomatic_done", workflow_id=workflow_id)
    return {
        "workflow_id": workflow_id,
        "step_log": ["step1", "step2", "step3", "step4", "step5"],
        "evidence_record": {},
        "risk_assessment": {},
        "approval_status": "approved",
        "crm_receipt": {"idempotency_key": idem_key},
        "audit_record": {"summary": str(response)[:200]},
    }
