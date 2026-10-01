from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class P1Measurements(BaseModel):
    """Pillar 1 — Durable Execution & Replayability."""
    resume_latency_ms: Optional[int] = None
    steps_re_executed_on_resume: Optional[int] = None       # target: 0
    duplicate_tool_calls_on_mid_write: Optional[int] = None # target: 0
    # opaque | parseable | human_readable
    checkpoint_format: Optional[str] = None
    # prevented_by_framework | prevented_by_config | not_prevented
    concurrent_resume_collision: Optional[str] = None
    manual_watchdog_required: Optional[bool] = None
    custom_code_lines_to_reach_score_3: int = 0
    # AHQ evidence: pause, SIGKILL, resume in a fresh process.
    resume_succeeded: Optional[bool] = None
    state_intact_after_kill: Optional[bool] = None
    side_effect_executions: Optional[int] = None  # target: 1 even with 2 concurrent resumers
    checkpoint_backend: Optional[str] = None


class P2Measurements(BaseModel):
    """Pillar 2 — Blast-Radius Containment."""
    runaway_loop_contained_by_default: Optional[bool] = None
    time_to_framework_halt_ms: Optional[int] = None
    credential_bleed_events: Optional[int] = None   # target: 0
    # framework_native | platform_sigterm | no_mechanism
    kill_switch_type: Optional[str] = None
    halt_latency_ms: Optional[int] = None
    isolation_requires_custom_code: Optional[bool] = None
    custom_code_lines_for_isolation: int = 0
    # RLC evidence: agent with a tool that never satisfies it.
    loop_halted_by_framework: Optional[bool] = None
    halt_signal: Optional[str] = None           # exception class or typed stop reason
    halt_signal_structured: Optional[bool] = None
    tool_calls_before_halt: Optional[int] = None
    configured_limit_honored: Optional[bool] = None
    model_self_terminated: Optional[bool] = None  # loop never happened -> inconclusive
    # SMA evidence: one specialist's tool raises.
    failure_propagation: Optional[str] = None   # contained | crashed_run | hung
    sibling_agents_completed: Optional[int] = None


class P3Measurements(BaseModel):
    """Pillar 3 — Observability-Nativeness."""
    required_attributes_emitted_by_default: list[str] = []
    missing_required_attributes: list[str] = []
    alert_fired_without_custom_code: Optional[bool] = None
    alert_latency_ms: Optional[int] = None
    custom_exporter_required: Optional[bool] = None
    custom_exporter_loc: int = 0
    proprietary_backend_required: Optional[bool] = None
    oss_stack_viable: Optional[bool] = None
    # SMA evidence, read back from Jaeger.
    framework_spans: Optional[int] = None
    trace_ids_per_run: Optional[int] = None     # target: 1
    orphan_spans: Optional[int] = None          # target: 0
    agents_invoked: Optional[int] = None
    agents_traced: Optional[int] = None


class P4Measurements(BaseModel):
    """Pillar 4 — Golden-Path Packageability."""
    template_creation_time_hrs: Optional[float] = None
    template_loc: int = 0
    framework_specific_hacks_required: list[str] = []
    policy_authorable_without_framework_internals: Optional[bool] = None
    required_framework_internal_hooks: list[str] = []
    one_day_deployment_achieved: Optional[bool] = None
    deployment_time_hrs: Optional[float] = None
    blockers_encountered: list[str] = []


class P5Measurements(BaseModel):
    """Pillar 5 — Day-2 Migration Fragility."""
    api_breaking_changes_in_patch: Optional[int] = None
    schema_breaking_changes_in_patch: Optional[int] = None
    checkpoint_migration_required: Optional[bool] = None
    prompt_rewrites_required: Optional[int] = None
    changelog_breaking_changes_per_release_avg: Optional[float] = None
    # Not scored. Set when an actual harness upgrade N→N+1 is performed.
    harness_upgrade_observed_hrs: Optional[float] = None
