"""Fixed conversation history for the context portability sub-test (P6).

HISTORY is a 4-message exchange in OpenAI neutral format. Each framework
attempts to load this history and answer FOLLOWUP. A correct response must
mention CONTEXT_KEYWORD (the distinctive bill amount) — proving the agent
read the prior context rather than hallucinating a fresh answer.
"""
from __future__ import annotations

HISTORY: list[dict] = [
    {
        "role": "user",
        "content": "What is the billing situation for customer cust-001?",
    },
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_bill_001",
                "type": "function",
                "function": {
                    "name": "get_bill",
                    "arguments": '{"customer_id": "cust-001"}',
                },
            }
        ],
    },
    {
        "role": "tool",
        "content": (
            "cust-001: last bill 142.50 EUR "
            "(plan 60.00, roaming 71.20, extras 11.30)."
        ),
        "tool_call_id": "call_bill_001",
    },
    {
        "role": "assistant",
        "content": (
            "Customer cust-001 has a bill of 142.50 EUR. "
            "The main cost driver is roaming charges at 71.20 EUR, "
            "followed by plan costs at 60.00 EUR."
        ),
    },
]

FOLLOWUP = (
    "Based on this billing history, would a roaming bundle help this customer? "
    "What specific amounts were involved in their last bill?"
)

CONTEXT_KEYWORD = "142"
