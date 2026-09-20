# Platform Operability Index (POI)

A reproducible benchmark for measuring the **production operability** of five Python agentic frameworks across two enterprise workflow scenarios.

> **TL;DR** — Most agentic framework evaluations stop at capability (can it reason? can it use tools?). POI measures what happens *after* you ship: checkpointing, blast-radius containment, observability nativeness, golden-path packaging, and upgrade fragility.

---

## Why POI?

Enterprise engineering teams adopting an agentic framework inherit its operability properties — good and bad. A framework that scores well on benchmark evals but lacks native checkpointing, emits no OTel spans, and breaks APIs on every patch release will cost your platform team hundreds of hours per year in custom scaffolding and upgrade work.

POI quantifies that cost as two numbers:
- **POI score** (0–15): higher is better — framework does more out of the box.
- **OT-LOC** (Operability Tax in lines of code): lower is better — less custom code your team must write.

---

## Frameworks Benchmarked

| ID | Framework | Version tested |
|---|---|---|
| F1 | [LangGraph](https://github.com/langchain-ai/langgraph) | ≥ 0.2 |
| F2 | [AutoGen / MS AgentChat](https://github.com/microsoft/autogen) | ≥ 0.4 |
| F3 | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | ≥ 0.1 |
| F4 | [Google ADK](https://github.com/google/adk-python) | ≥ 0.1 |
| F5 | [Strands Agents](https://github.com/strands-agents/sdk-python) | ≥ 0.1 |

---

## The Five Pillars

Each pillar is scored 0–3 by the harness. Scores are **objective**: the harness either observes the property or it does not.

### P1 — Durable Execution & Replayability
Can the framework checkpoint mid-run, resume after a crash, and guarantee idempotent tool calls?

| Score | Criterion |
|---|---|
| 0 | No checkpoint mechanism; full replay on failure |
| 1 | Checkpoint exists but requires custom serialisation |
| 2 | Native checkpoint with parseable format; resume works |
| 3 | Portable checkpoint (cross-process, cross-node); concurrent-resume safe |

**Tests:** T1 baseline run, T2 mid-flight resume latency, T3 idempotency (duplicate tool call count), T4 checkpoint format introspection, T5 concurrent-resume collision check.

### P2 — Blast-Radius Containment
Does the framework limit runaway loops and support platform-level kill switches without custom code?

| Score | Criterion |
|---|---|
| 0 | No mechanism; runaway agent consumes unbounded resources |
| 1 | Platform SIGTERM is the only kill switch (requires ops intervention) |
| 2 | Configurable loop budget (max_iterations / recursion_limit) |
| 3 | Active containment: framework catches runaway at runtime and surfaces structured error |

**Tests:** FI-3 (inject infinite loop, measure containment time), FI-4 (credential poisoning isolation).

### P3 — Observability Nativeness
Does the framework emit OpenTelemetry Gen-AI semantic convention spans without custom exporters?

| Score | Criterion |
|---|---|
| 0 | No OTel spans emitted |
| 1 | Some spans but missing required Gen-AI attributes |
| 2 | All required attributes present; custom exporter still needed |
| 3 | Full OTel Gen-AI compliance out of the box; no custom exporter required |

**Required attributes:** `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`.

### P4 — Golden-Path Packageability
Can the framework be packaged as a Helm chart that passes Kyverno policy enforcement with minimal custom YAML?

| Score | Criterion |
|---|---|
| 0 | No Helm-compatible packaging path |
| 1 | Helm chart requires > 200 lines of custom templates |
| 2 | Helm chart 100–200 lines; manual Kyverno workarounds needed |
| 3 | Helm chart < 100 lines; passes all Kyverno ClusterPolicies without hacks |

**Kyverno policies enforced:** CHECKPOINT_BACKEND_URL set, OTEL_EXPORTER_OTLP_ENDPOINT set, tenant label present, resource limits declared, secrets via `secretKeyRef` only.

### P5 — Day-2 Migration Fragility
How often does a patch-level upgrade require code changes, schema migrations, or prompt rewrites?

| Score | Criterion |
|---|---|
| 0 | > 3 breaking changes per release on average |
| 1 | 1–3 breaking changes per release on average |
| 2 | < 1 breaking change per release; no schema migration required |
| 3 | Zero breaking changes in patch; stable checkpoint schema; no prompt rewrites |

**Measurement:** desk research on changelog history + `api_breaking_changes_in_patch`, `checkpoint_migration_required`, `prompt_rewrites_required` fields.

---

## Benchmark Results

### Score Matrix

| Framework | P1 | P2 | P3 | P4 | P5 | **POI** |
|---|---|---|---|---|---|---|
| LangGraph (F1) | 2 | **3** | 1 | 2 | 1 | **9** |
| AutoGen/MS (F2) | 0 | 1 | 1 | 2 | 1 | 5 |
| OpenAI SDK (F3) | 0 | 1 | 1 | 2 | **3** | 7 |
| Google ADK (F4) | 2 | 1 | 1 | 2 | 2 | 8 |
| Strands (F5) | 0 | 1 | **2** | **3** | **3** | **9** |

### Operability Tax (OT-LOC)

Lines of custom code your team must write to reach production-grade operability:

| Framework | OT-LOC | POI |
|---|---|---|
| OpenAI SDK | 124 | 7 |
| AutoGen/MS | 135 | 5 |
| LangGraph | 179 | **9** |
| Strands | 195 | **9** |
| Google ADK | 221 | 8 |

### Ranking

1. **LangGraph** — POI 9, OT 179 LOC. Wins P2 outright (native recursion-limit catches runaway loops with a structured `GraphRecursionError`). Strongest checkpoint story (MemorySaver → PostgresSaver without code change).
2. **Strands** — POI 9, OT 195 LOC. Best P4 (leanest Helm chart) and ties P5 (most stable API). Loses P1 because checkpoint/resume requires a custom state-serialisation wrapper.
3. **Google ADK** — POI 8, OT 221 LOC. Solid P1 via `InMemorySessionService` (parseable format); highest OT because the session backend swap and LiteLLM routing layer add scaffolding.
4. **OpenAI SDK** — POI 7, OT 124 LOC. Lowest OT of all — but checkpoint state lives in OpenAI's backend and is not portable. Excellent P5 (most stable changelog).
5. **AutoGen/MS** — POI 5, OT 135 LOC. Weakest durability (no native checkpoint); high P5 cost (3+ breaking changes per release on average).

---

## Scenarios

### GEW — Generic Enterprise Workflow

A 5-step approval chain representative of common enterprise automation patterns:

```
step1_data_retrieval → step2_risk_assessment → step3_hitl_gate → step4_action_execution → step5_audit
```

**Mock infrastructure** (FastAPI servers, all DRY_RUN-aware):
- `mock_api_server` (port 8001) — external data fetch + risk scoring
- `mock_crm_server` (port 8002) — idempotent CRM write (idempotency key → receipt)
- `approval_server` (port 8003) — human-in-the-loop gate (submit → poll → approve)

**Fixed implementation:** all 5 frameworks execute the same linear DAG with identical tool signatures — ensuring apples-to-apples comparison.

**Idiomatic implementation:** each framework uses its native patterns:
- **LangGraph:** conditional edges (`route_after_risk`) — low-risk bypasses HITL gate
- **AutoGen:** `RoundRobinGroupChat` + `TextMentionTermination`
- **OpenAI SDK:** hub-and-spoke `Agent` handoffs (Orchestrator → specialists)
- **Google ADK:** single `LlmAgent` with all tools (vs `SequentialAgent` in fixed)
- **Strands:** single orchestrator Agent with all 7 tools

### TCW — Telco CVM/NBA Workflow

A 5-step customer value management / next-best-action workflow representative of telco/retail personalisation:

```
graph_query → propensity_score → eligibility_check → offer_personalize → channel_dispatch
```

**Mock infrastructure** (FastAPI servers, all DRY_RUN-aware):
- `neo4j_stub` (port 8101) — customer 360 graph data (segment, tenure, products, opt-out)
- `ml_endpoint` (port 8102) — propensity scoring + eligibility rule engine
- `channel_adapter` (port 8103) — multi-channel dispatch (email / SMS / push) + receipt audit

**Fixed implementation:** same linear DAG across all 5 frameworks.

**Idiomatic implementation:** native patterns per framework (LangGraph routes empty eligibility → skips personalisation; AutoGen uses `SelectorGroupChat` for dynamic step routing; etc.).

---

## Harness Architecture

```
platform-operability-index/
├── harness/
│   ├── run_all.py                   # Full benchmark runner (all 20 combos)
│   ├── full_run.py                  # Single-framework runner (subprocess mode)
│   ├── runner.py                    # CLI entry point
│   ├── adapters/
│   │   ├── base.py                  # SubprocessRunner (venv isolation)
│   │   ├── registry.py              # Auto-discovery of adapter dirs
│   │   ├── shared/tcw_p1.py        # Shared TCW T1 validator
│   │   ├── langgraph/               # F1: adapter, p1–p5 measure, run.py, requirements
│   │   ├── ms_agent/                # F2: AutoGen adapter
│   │   ├── openai_sdk/              # F3: OpenAI Agents SDK adapter
│   │   ├── google_adk/              # F4: Google ADK adapter
│   │   └── strands/                 # F5: Strands adapter
│   └── shared/
│       ├── measurement.py           # RunResult, RunMetadata, PillarScores (Pydantic)
│       ├── pillar_models.py         # P1–P5 measurement Pydantic models
│       ├── scoring.py               # score_p1…score_p5 pure functions
│       ├── failure_injector.py      # FI-1…FI-4 test utilities
│       ├── otel_probe.py            # Prometheus/OTel attribute probing
│       └── llm.py                   # AI Refinery LLM factory
├── scenarios/
│   ├── gew/
│   │   ├── shared/mock_client.py   # Framework-agnostic HTTP client
│   │   ├── mock_infrastructure/    # 3 FastAPI mock servers + docker-compose
│   │   └── implementations/
│   │       ├── langgraph/fixed/ idiomatic/
│   │       ├── ms_agent/fixed/ idiomatic/
│   │       ├── openai_agents_sdk/fixed/ idiomatic/
│   │       ├── google_adk/fixed/ idiomatic/
│   │       └── strands_agents/fixed/ idiomatic/
│   └── tcw/
│       ├── shared/mock_client.py   # DRY_RUN-aware HTTP client
│       ├── mock_infrastructure/    # neo4j_stub, ml_endpoint, channel_adapter
│       └── implementations/        # same 5 × fixed/idiomatic structure
├── charts/
│   ├── poi-langgraph/               # Helm chart — passes all Kyverno policies
│   ├── poi-ms-agent/
│   ├── poi-openai-sdk/
│   ├── poi-google-adk/
│   └── poi-strands/
├── infrastructure/
│   └── kyverno/                     # ClusterPolicy definitions
├── analysis/
│   ├── poi_report.py               # Article-ready score matrix + OT + ranking
│   ├── score_matrix.py             # Raw score matrix (all 20 combos)
│   └── ot_summary.py               # OT aggregation
└── results/
    └── runs/                        # YAML per run (20 files after full run)
```

### Key Design Decisions

**Subprocess isolation.** Each adapter (`run.py`) runs in its own process with its own `requirements.txt` and optional `.venv`. This prevents framework library conflicts (e.g., different Pydantic versions) and mirrors production isolation.

**DRY_RUN=true.** Every workflow implementation checks `os.environ["DRY_RUN"] == "true"` and returns canned fixtures without making LLM calls or hitting external services. The full benchmark runs in CI with no credentials.

**Fixed vs idiomatic implementations.** Fixed runs establish a common DAG baseline (apples-to-apples). Idiomatic runs show each framework in its natural mode. P1–P5 scores are framework properties, not scenario-dependent — scores are identical across GEW/TCW and fixed/idiomatic, as expected.

**Pydantic v1/v2 compatibility.** The harness shared layer works with both versions: all serialisation routes through `model_dump_json()` (v2) / `.json()` (v1) → `json.loads()` → PyYAML, avoiding enum-tagging bugs.

**OT-LOC measurement.** Operability Tax is the sum of custom lines needed to reach score-3 behaviour:
- `custom_code_lines_to_reach_score_3` — P1 checkpoint wrapper
- `custom_code_lines_for_isolation` — P2 kill-switch glue
- `custom_exporter_loc` — P3 OTel exporter shim
- `template_loc` — P4 Helm template count

---

## Running the Benchmark

### Prerequisites

```bash
python3 -m pip install pydantic pyyaml structlog requests
```

### DRY_RUN (no credentials required)

```bash
cd platform-operability-index
DRY_RUN=true python3 -m harness.run_all
```

Writes 20 YAML files to `results/runs/`.

### Generate report

```bash
python3 analysis/poi_report.py
```

### With real LLM (AI Refinery)

```bash
export AIREFINERY_BASE_URL=https://your-endpoint
export AIREFINERY_API_KEY=your-key
export AIREFINERY_MODEL_ID=gpt-4o

# Start mock infrastructure
cd scenarios/gew/mock_infrastructure && docker compose up -d
cd scenarios/tcw/mock_infrastructure && docker compose up -d

python3 -m harness.run_all
```

### Single framework

```bash
DRY_RUN=true python3 -m harness.full_run --framework F1 --scenario GEW --impl fixed
```

---

## Scoring Logic

All scoring functions are pure Python in [`harness/shared/scoring.py`](harness/shared/scoring.py). Each takes a typed Pydantic model and returns 0–3.

Example — P2 scoring:

```python
def score_p2(m: P2Measurements) -> int:
    if m.runaway_loop_contained_by_default:
        return 3
    if m.configurable_loop_budget:
        return 2
    if m.kill_switch_mechanism == "platform_sigterm":
        return 1
    return 0
```

P1–P5 measurement models are in [`harness/shared/pillar_models.py`](harness/shared/pillar_models.py). All fields are `Optional` with `None` defaults — missing data produces a 0 score, not an error.

---

## Extending the Benchmark

### Add a new framework

1. Create `harness/adapters/<name>/` with `adapter.py`, `run.py`, `requirements.txt`, `metadata.json`.
2. Implement `_run_p1` through `_run_p5` — raise `NotImplementedError` for pillars not yet measured.
3. Add `scenarios/gew/implementations/<name>/fixed/workflow.py` and `idiomatic/workflow.py`.
4. Add `scenarios/tcw/implementations/<name>/fixed/workflow.py` and `idiomatic/workflow.py`.
5. Add the framework to `_ADAPTERS` in `harness/run_all.py`.

### Add a new pillar

1. Add a new Pydantic model to `harness/shared/pillar_models.py`.
2. Add a `score_pN()` function to `harness/shared/scoring.py`.
3. Wire `_run_pN()` in each adapter.

### Add a new scenario

1. Create `scenarios/<name>/shared/mock_client.py` with DRY_RUN bypasses.
2. Create `scenarios/<name>/mock_infrastructure/` servers.
3. Create `scenarios/<name>/implementations/<fw>/fixed/workflow.py` for each framework.
4. Add `ScenarioId.<NAME>` to `harness/shared/measurement.py`.
5. Add the scenario to `_SCENARIOS` in `harness/run_all.py`.

---

## Engineering Standards

This codebase enforces:
- **150-line file limit** (non-blank, non-comment) — every file stays within SRP scope.
- **No hardcoded URLs, credentials, or service addresses** — all via env vars.
- **Secrets via `secretKeyRef` only** in Helm charts — never `value:`.
- **Structured JSON logs** via `structlog` — no bare `print()` in application code.
- **Pydantic v1/v2 compatible serialisation** throughout the harness shared layer.
- **DRY_RUN=true** makes every workflow runnable in CI with zero external dependencies.

---

## License

Private research benchmark. All rights reserved.
