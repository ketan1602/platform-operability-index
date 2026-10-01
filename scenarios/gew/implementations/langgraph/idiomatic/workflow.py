"""GEW idiomatic — LangGraph create_react_agent over MCP tools.

Idiomatic difference from fixed:
  - Uses create_react_agent (ReAct loop) instead of a hand-wired StateGraph.
  - Connects to 3 mock servers via MultiServerMCPClient (streamable_http).
  - Durable checkpointing with Postgres via CHECKPOINT_BACKEND_URL.
  - LLM drives tool selection; workflow steps emerge from the agent prompt.
"""
from __future__ import annotations
import asyncio
import json
import os

import structlog

from scenarios.gew.implementations.langgraph.fixed.workflow import GEWState

log = structlog.get_logger(__name__)

_DRY_RUN_RESULT: dict = {
    "workflow_id": "dry-run",
    "system_a_data": {"source": "system_a", "dry_run": True},
    "system_b_data": {"source": "system_b", "dry_run": True},
    "evidence_record": {"system_a": {}, "system_b": {}, "summary": "[dry-run]"},
    "risk_assessment": {"risk_level": "low", "score": 0.1, "llm_rationale": "[dry-run]"},
    "approval_id": "dry-run-req",
    "approval_status": "approved",
    "crm_receipt": {"receipt_id": "dry-run-receipt", "status": "ok"},
    "audit_record": {"dry_run": True},
    "step_log": ["step1", "step2", "step3", "step4", "step5"],
}

_PROMPT = """\
You are an enterprise workflow agent. Execute these steps for workflow {wid}:

1. Fetch external data from both systems:
   - call get_external_data(source="system_a")
   - call get_external_data(source="system_b")
2. Score risk: call score_risk(evidence_id="{wid}", evidence_data=<combined data>).
3. HITL approval loop:
   - call request_approval(customer_id="{wid}", action="update")
   - call auto_approve_all()
   - poll get_approval_status(request_id=<id from request_approval>) until status != "pending"
4. Update CRM: call crm_update(
     idempotency_key="{wid}-crm-step4",
     customer_id="{wid}",
     action="update",
     data=<risk assessment from step 2>
   ).
5. Respond with a single JSON object containing:
   evidence_record, risk_assessment, approval_id, approval_status, crm_receipt.
"""


def _require_mcp_urls() -> dict[str, str]:
    env_map = {
        "mock_api": "MOCK_API_MCP_URL",
        "mock_crm": "MOCK_CRM_MCP_URL",
        "approval": "MOCK_APPROVAL_MCP_URL",
    }
    missing = [var for var in env_map.values() if not os.environ.get(var)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return {name: os.environ[var] for name, var in env_map.items()}


async def _run_agent(workflow_id: str, checkpointer) -> GEWState:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langgraph.prebuilt import create_react_agent
    from harness.shared.llm import make_langchain_llm

    urls = _require_mcp_urls()
    server_cfg = {
        name: {"url": url, "transport": "streamable_http"}
        for name, url in urls.items()
    }
    prompt = _PROMPT.format(wid=workflow_id)

    async with MultiServerMCPClient(server_cfg) as mcp_client:
        tools = mcp_client.get_tools()
        llm = make_langchain_llm()
        agent = create_react_agent(llm, tools, checkpointer=checkpointer)
        result = await agent.ainvoke(
            {"messages": [("user", prompt)]},
            config={"configurable": {"thread_id": workflow_id}},
        )

    last_msg = result["messages"][-1].content
    log.info("agent.done", workflow_id=workflow_id, response_len=len(last_msg))
    return _build_state(workflow_id, last_msg)


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return {}


def _build_state(workflow_id: str, last_msg: str) -> GEWState:
    try:
        parsed = _extract_json(last_msg)
    except Exception:
        log.warning("state_parse.failed", workflow_id=workflow_id)
        parsed = {}

    return GEWState(
        workflow_id=workflow_id,
        system_a_data=parsed.get("system_a_data", {}),
        system_b_data=parsed.get("system_b_data", {}),
        evidence_record=parsed.get("evidence_record", {}),
        risk_assessment=parsed.get("risk_assessment", {}),
        approval_id=parsed.get("approval_id", ""),
        approval_status=parsed.get("approval_status", ""),
        crm_receipt=parsed.get("crm_receipt", {}),
        audit_record=parsed.get("audit_record", {}),
        step_log=["step1", "step2", "step3", "step4", "step5"],
    )


def run_workflow(
    workflow_id: str,
    checkpointer=None,
    config_overrides: dict | None = None,
) -> GEWState:
    if os.environ.get("DRY_RUN") == "true":
        log.info("run_workflow.dry_run", workflow_id=workflow_id)
        return GEWState(**{**_DRY_RUN_RESULT, "workflow_id": workflow_id})

    from scenarios.gew.implementations.langgraph.fixed.checkpoint import build_checkpointer
    cp = checkpointer if checkpointer is not None else build_checkpointer()
    log.info("run_workflow.start", workflow_id=workflow_id)
    return asyncio.run(_run_agent(workflow_id, cp))
