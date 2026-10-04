from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class HackRecord(BaseModel):
    """A single K8s/deployment workaround with its operational cost."""
    description: str
    cost_hrs: float = 0.0              # one-time implementation + debug hours
    recurring_hrs_per_yr: float = 0.0  # annual maintenance burden
    upgrade_sensitive: bool = False    # likely to break on framework version bump


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
    # SMA Trial C: concurrent in-process PORT workflow invocations
    concurrent_tenancy_safe: Optional[bool] = None  # True = no cross-contamination


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
    framework_specific_hacks_required: list[HackRecord] = []
    policy_authorable_without_framework_internals: Optional[bool] = None
    required_framework_internal_hooks: list[str] = []
    one_day_deployment_achieved: Optional[bool] = None
    deployment_time_hrs: Optional[float] = None
    blockers_encountered: list[str] = []
    # K8s fit sub-tests
    lazy_init_s: Optional[float] = None       # seconds to import; -1.0 = eager creds
    lazy_init_ms: Optional[int] = None        # import time in ms (-1 = eager cred check)
    sigterm_graceful: Optional[bool] = None   # exits within 3s on SIGTERM
    sigterm_latency_ms: Optional[int] = None  # SIGTERM→exit latency in ms
    # HITL gate: LOC to add human-in-the-loop approval to a baseline workflow
    hitl_gate_loc: Optional[int] = None
    hitl_gate_latency_ms: Optional[int] = None  # approval file write → process exit, ms
    hitl_native: Optional[bool] = None    # True = framework provides a first-class HITL abstraction
    hitl_verified: Optional[bool] = None  # HITL approval gate works end-to-end (empirical)
    # Pod spec diff probe: env var names in the chart not present in the baseline set
    hacks_detected_in_pod: list[str] = []


class P5Measurements(BaseModel):
    """Pillar 5 — Day-2 Migration Fragility (empirically probed)."""
    version_before: Optional[str] = None
    version_after: Optional[str] = None
    harness_failures_after_upgrade: int = 0
    api_breaking_post_patch: int = 0
    schema_breaking_post_patch: int = 0
    checkpoint_migration_required: bool = False
    fleet_upgrade_probe_wall_s: Optional[float] = None
    residual_manual_failures: int = 0
    regressions: list[dict] = []   # field-level before/after changes from diff


class P6Measurements(BaseModel):
    """Pillar 6 — Tool invocation quality and portability."""
    tools_called_unmodified: int = 0           # 0-3: plain tools the LLM actually invoked
    task_completed: Optional[bool] = None       # agent finished the three-step task
    state_json_safe: Optional[bool] = None      # raw framework result JSON-serializable (informational)
    port_reuse_rate: Optional[float] = None     # avg reuse rate when porting FROM this framework
    port_changed_lines: Optional[int] = None    # avg lines changed when porting FROM this framework
    context_portable: Optional[bool] = None     # agent resumed correctly from neutral history
    context_injection: Optional[str] = None     # "native" | "prompt_fallback"
    cross_venv_success_rate: Optional[float] = None  # fraction of ported SMA workflows that run successfully


class P7Measurements(BaseModel):
    """Pillar 7 — Developer Experience (timed + error clarity + ecosystem)."""
    time_to_first_run_s: Optional[float] = None    # wall-clock seconds for smoke test
    ttr_score: Optional[int] = None                # 0-3 derived from time_to_first_run_s
    error_clarity_a: Optional[int] = None          # wrong return type error (Mistake A)
    error_clarity_b: Optional[int] = None          # missing arg error (Mistake B)
    error_clarity_c: Optional[int] = None          # bad LLM init error (Mistake C)
    error_clarity_d: Optional[int] = None          # returns None instead of str (Mistake D)
    error_clarity_e: Optional[int] = None          # wrong type annotation (Mistake E)
    functional_verified: Optional[bool] = None     # agent completed smoke task end-to-end
    p7_score: Optional[int] = None                 # 0-3 weighted
    middleware_injectable: Optional[bool] = None   # callback fires on tool call without class change
    local_testability_score: Optional[int] = None  # 0-3: error clarity when no cloud creds present
    escape_hatch_score: Optional[int] = None       # 0-3: probes passed (custom endpoint/env/tracing)
    community_score: Optional[int] = None          # 0-3 static: OSS ecosystem size + adoption
    vendor_independence_score: Optional[int] = None # 0-3 static: lock-in risk to vendor cloud


class P9Measurements(BaseModel):
    """Pillar 9 — Ops Experience: FinOps + Runtime + Fleet management."""
    input_tokens_per_run: Optional[int] = None          # LLM input tokens for a representative run
    agent_run_latency_ms: Optional[int] = None          # end-to-end wall ms for a smoke run
    concurrent_throughput_ratio: Optional[float] = None # N=3 vs N=1; ≥ 1.0 means linear scaling
    cross_worker_resume: Optional[bool] = None          # checkpoint survives SIGKILL + new worker
    peak_rss_mb: Optional[float] = None                 # peak child RSS in MB during primary run
    avg_cpu_percent: Optional[float] = None             # mean child CPU % during primary run


class P8Measurements(BaseModel):
    """Pillar 8 — Framework Security Enforcement (framework-level, not LLM safety).

    Sub-tests confirm the FRAMEWORK enforces security boundaries independent of
    what the LLM generates. All three are structural or telemetry checks — no
    LLM safety behaviour is measured.
    """
    tool_scope_enforced: Optional[bool] = None         # framework blocks wrong-agent tool calls
    context_isolation_verified: Optional[bool] = None  # Agent B cannot see Agent A's private data
    telemetry_clean: Optional[bool] = None             # framework spans/logs don't expose POI_SEC_SENTINEL
    k8s_scope_enforced: Optional[bool] = None          # K8s RBAC blocks cross-namespace secret reads
    admission_blocked: Optional[bool] = None           # Kyverno blocks privileged pod creation
    http_cred_bleed_events: Optional[int] = None       # HTTP calls to mock-auth that leaked POI_BLEED_TOKEN
    trace_spans_clean: Optional[bool] = None           # no raw HTTP LLM spans without gen-ai semconv
    p8_score: Optional[int] = None                     # 0-3 weighted sum of 6 sub-tests
