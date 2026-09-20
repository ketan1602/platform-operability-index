"""Shared TCW P1 T1 validation — called from all five adapters.

Imports and runs the TCW workflow for the given framework and impl_type,
then asserts that all five TCW step names appear in step_log.
Returns without raising if the check passes.
"""
from __future__ import annotations

_TCW_STEPS = frozenset([
    "graph_query",
    "propensity_score",
    "eligibility_check",
    "offer_personalize",
    "channel_dispatch",
])

_FW_MODULE = {
    "F1": "langgraph",
    "F2": "ms_agent",
    "F3": "openai_agents_sdk",
    "F4": "google_adk",
    "F5": "strands_agents",
}


def validate_tcw_t1(framework_id: str, impl_type: str) -> None:
    """Import and run the TCW T1 baseline for framework_id and impl_type."""
    fw = _FW_MODULE.get(framework_id)
    if fw is None:
        raise ValueError(f"Unknown framework_id: {framework_id}")
    mod_path = f"scenarios.tcw.implementations.{fw}.{impl_type}.workflow"
    wf = __import__(mod_path, fromlist=["run_workflow"])
    result = wf.run_workflow(workflow_id=f"p1-t1-tcw-{framework_id}-{impl_type}")
    step_log = set(result.get("step_log") or [])
    missing = _TCW_STEPS - step_log
    if missing:
        raise AssertionError(
            f"TCW T1 [{framework_id}/{impl_type}]: missing steps {sorted(missing)}"
        )
