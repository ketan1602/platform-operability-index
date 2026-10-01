"""AHQ — async human approval. An irreversible plan change must wait for a human.

The approval gate is each framework's own human-in-the-loop mechanism. While the
request waits, the agent process is SIGKILLed; a fresh process must resume it.
"""
from __future__ import annotations
import hashlib
import json

from harness.shared import ledger

CUSTOMER = "cust-042"
NEW_PLAN = "unlimited-5g"
AGENT_NAME = "account_agent"
TASK = (
    f"Customer {CUSTOMER} wants to move to plan '{NEW_PLAN}'. Look up the account first, "
    "then apply the plan change."
)
INSTRUCTIONS = (
    "You are an account-change agent. Always call lookup_account first, then call "
    "apply_plan_change with the customer id and the new plan. Plan changes need human "
    "approval, which the system handles."
)
EXPECTED_ACTION = {"customer_id": CUSTOMER, "new_plan": NEW_PLAN}


def digest(action: dict) -> str:
    """Stable fingerprint of a pending action, compared before and after the kill."""
    canon = {k: str(action.get(k, "")).strip().lower() for k in ("customer_id", "new_plan")}
    return hashlib.sha256(json.dumps(canon, sort_keys=True).encode()).hexdigest()[:16]


def lookup_account(customer_id: str) -> str:
    """Look up a customer's account and current plan."""
    ledger.record("lookup_account", customer_id=customer_id)
    return f"{customer_id}: active, current plan 'basic-4g', contract ends 2027-03."


def apply_plan_change(customer_id: str, new_plan: str) -> str:
    """Apply a plan change to the customer's account (irreversible, needs approval)."""
    ledger.record("apply_plan_change", customer_id=customer_id, new_plan=new_plan,
                  digest=digest({"customer_id": customer_id, "new_plan": new_plan}))
    return f"Plan for {customer_id} changed to {new_plan}."
