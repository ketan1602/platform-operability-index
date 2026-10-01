"""SMA — supervisor multi-agent. A supervisor delegates to three telco specialists.

With POI_SMA_FAULT=1 the network specialist's tool raises, simulating an OSS outage.
The question is whether that failure stays inside the network specialist.
"""
from __future__ import annotations
import os

from harness.shared import ledger

CUSTOMER = "cust-001"
SUPERVISOR = "supervisor"
SPECIALISTS = ("billing_agent", "network_agent", "retention_agent")
TASK = (
    f"Customer {CUSTOMER} says their bill is too high, calls keep dropping, and they want "
    "to cancel. Consult the billing, network and retention specialists (each of them), "
    "then give one combined recommendation."
)
SUPERVISOR_INSTRUCTIONS = (
    "You are a telco customer-care supervisor. You never answer from your own knowledge: "
    "delegate to billing_agent, network_agent and retention_agent, one call each, passing "
    "the customer id. If a specialist fails, continue with the others. Then combine."
)
SPECIALIST_INSTRUCTIONS = {
    "billing_agent": "You are the billing specialist. Use get_bill for the customer id, then summarise it.",
    "network_agent": "You are the network specialist. Use check_network for the customer id, then summarise it.",
    "retention_agent": "You are the retention specialist. Use get_retention_offer for the customer id, then summarise it.",
}
SPECIALIST_DESCRIPTIONS = {
    "billing_agent": "Billing specialist: explains a customer's bill. Input: the customer id.",
    "network_agent": "Network specialist: checks a customer's network quality. Input: the customer id.",
    "retention_agent": "Retention specialist: finds a retention offer. Input: the customer id.",
}


def fault_injected() -> bool:
    return os.environ.get("POI_SMA_FAULT") == "1"


def get_bill(customer_id: str) -> str:
    """Return the customer's latest bill breakdown."""
    ledger.record("get_bill", customer_id=customer_id)
    return f"{customer_id}: last bill 142.50 EUR (plan 60.00, roaming 71.20, extras 11.30)."


def check_network(customer_id: str) -> str:
    """Return network quality at the customer's home cell."""
    ledger.record("check_network", customer_id=customer_id, fault=fault_injected())
    if fault_injected():
        raise RuntimeError("network OSS timeout: cell-quality service unavailable")
    return f"{customer_id}: home cell 4G-1182 dropped-call rate 6.1% (threshold 2%)."


def get_retention_offer(customer_id: str) -> str:
    """Return the best retention offer for the customer."""
    ledger.record("get_retention_offer", customer_id=customer_id)
    return f"{customer_id}: eligible for 12 months roaming bundle at 9.99 EUR/month."


TOOLS_BY_SPECIALIST = {
    "billing_agent": get_bill,
    "network_agent": check_network,
    "retention_agent": get_retention_offer,
}
TOOL_EVENTS = {"billing_agent": "get_bill", "network_agent": "check_network",
               "retention_agent": "get_retention_offer"}
