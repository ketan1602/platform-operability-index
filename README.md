# Platform Operability Index (POI)

A reproducible benchmark for measuring the **production operability** of five Python agentic frameworks across realistic enterprise workflow scenarios.

---

## 1. The Problem

Most agentic framework evaluations stop at capability: can it reason, can it use tools, does it pass the task? That is the wrong question for an enterprise platform team.

The question that matters in production is: **what does the framework cost to operate at scale?**

A framework that scores well on capability benchmarks but lacks native checkpointing will force your platform team to write custom crash-recovery wrappers. One that emits no OpenTelemetry spans means your SRE team flies blind when an agent loop misbehaves at 2am. One that ships breaking API changes on patch releases turns every quarterly upgrade into a multi-team coordination event.

These costs are real, recurring, and rarely measured. They compound: a team that spends two weeks writing checkpoint scaffolding is also the team that falls behind on feature delivery, delays the next framework upgrade, and accumulates technical debt that future teams inherit.

---

## 2. What is POI?

POI quantifies the operational cost of a framework as two numbers:

- **POI score (0–27):** how much the framework provides out of the box across 9 pillars (0–3 each). Higher = less work for your platform team.
- **OT-LOC (Operability Tax, lines of code):** how much custom scaffolding your team must write to reach production-grade operability. Lower = less ongoing maintenance burden.

### Nine Pillars

| Pillar | What it measures |
|--------|-----------------|
| P1 — Durable Execution | Checkpoint + resume after a hard crash (SIGKILL); idempotency under concurrent resume |
| P2 — Blast-Radius Containment | Runaway loop halting; fault isolation so one specialist's failure doesn't crash the run |
| P3 — Observability Nativeness | OTel Gen-AI span attributes, connected traces, custom exporter cost |
| P4 — Packageability | Kubernetes / Helm deployability; K8s fit (lazy init, SIGTERM, HITL gate) |
| P5 — Migration Fragility | Breaking-change frequency; checkpoint schema stability across releases |
| P6 — Tool Quality | Plain-function tool acceptance; portability of tool definitions across frameworks |
| P7 — Developer Experience | Time-to-first-run; error clarity; middleware injection; ecosystem and vendor independence |
| P8 — Security | Tool scope enforcement; context isolation; telemetry cleanliness; credential bleed |
| P9 — Ops Experience | Token cost, latency, concurrency throughput, resource footprint, cross-worker resume |

### Scoring Rubric (per pillar)

| Score | Meaning |
|-------|---------|
| 0 | The property is absent — you must build it from scratch |
| 1 | The property exists but requires significant custom scaffolding |
| 2 | The property works but with manual operator configuration |
| 3 | The property is fully native — the framework handles it without custom code |

### Frameworks Benchmarked

| ID | Framework | What it is |
|----|-----------|------------|
| F1 | [LangGraph](https://github.com/langchain-ai/langgraph) | Graph-based stateful agent orchestration by LangChain |
| F2 | [AutoGen / MS AgentChat](https://github.com/microsoft/autogen) | Microsoft's multi-agent conversation framework |
| F3 | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | OpenAI's first-party agent SDK with hosted state |
| F4 | [Google ADK](https://github.com/google/adk-python) | Google's Agent Development Kit, Cloud Run-native |
| F5 | [Strands Agents](https://github.com/strands-agents/sdk-python) | AWS-backed lightweight agent framework |

---

## 3. Setup & Execution

### Prerequisites

- **Python 3.12+** — [python.org/downloads](https://www.python.org/downloads/)
- **`uv`** — fast Python package manager used by `setup_venvs.sh`:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS / Linux
  # or: pip install uv
  ```
- **[OrbStack](https://orbstack.dev/)** (or any Kubernetes cluster) — for live infra runs only; not needed for dry-run
- **An API key for at least one LLM provider** (see below)

### Install

Each framework has conflicting dependencies, so each gets its own venv:

```bash
./setup_venvs.sh
```

This creates `.venv/` under each adapter directory (`harness/adapters/{langgraph,ms_agent,openai_sdk,google_adk,strands}/`).

### Configure secrets

```bash
cp .env.example .env
```

The harness uses a **provider-agnostic LLM config** — set the three variables below for whichever provider you have access to. All five framework adapters route through the same endpoint.

#### Option A — OpenAI

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
MODEL_ID=gpt-4o
```

#### Option B — Anthropic (Claude)

```bash
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_API_KEY=sk-ant-...
MODEL_ID=claude-sonnet-4-5
```

> Anthropic's API uses different request/response shapes from OpenAI. The harness LLM client detects `anthropic.com` in `LLM_BASE_URL` and switches to the `anthropic` SDK path automatically.

#### Option C — AI Refinery (Accenture internal)

```bash
LLM_BASE_URL=https://<your-refinery-host>/v1
LLM_API_KEY=<airefinery-key>
MODEL_ID=openai/gpt-oss-120b
AIREFINERY_SDK_VERSION=2          # optional — defaults to 2
```

AI Refinery exposes an OpenAI-compatible `/v1/chat/completions` endpoint, so no special handling is needed beyond the three standard variables.

#### Option D — Any OpenAI-compatible endpoint (Ollama, Azure OpenAI, LiteLLM proxy, etc.)

```bash
LLM_BASE_URL=http://localhost:11434/v1   # example: Ollama
LLM_API_KEY=ollama                        # placeholder; Ollama ignores the key
MODEL_ID=llama3.2
```

Set `LLM_BASE_URL` to any endpoint that speaks the OpenAI `/v1/chat/completions` protocol and the harness will use it without code changes.

### Dry-run (no LLM calls, no infrastructure)

Verifies the harness wiring, scoring, and output format using canned fixtures:

```bash
DRY_RUN=true python3 -m harness.run_all --scenarios GEW TCW
```

### Live run (real LLM, real infrastructure)

Bring up the backing services first (Postgres, RabbitMQ, Neo4j, Jaeger — all port-forwarded from the cluster):

```bash
./deploy-mocks.sh        # deploy mock server pods once
./infra.sh up            # port-forward all services; writes .env.infra
```

Then run the benchmark:

```bash
# All frameworks, all scenarios, 5 repeats each (median scoring)
./run_bench.sh

# Subset — specific frameworks and scenarios
./run_bench.sh --frameworks F1 F5 --scenarios RLC SMA AHQ --repeats 3

# Single scenario, single framework
./run_bench.sh --frameworks F1 --scenarios AHQ --repeats 1
```

Tear down when done:

```bash
./infra.sh down
```

### Generate the report

```bash
python3 analysis/poi_report.py
```

Results are written to `results/` as YAML (one file per run) and the report produces the score matrix, OT-LOC table, sensitivity analysis, and per-pillar evidence summaries.

### Key environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_BASE_URL` | — | LLM API base URL (any OpenAI-compatible endpoint) |
| `LLM_API_KEY` | — | API key for the chosen provider |
| `MODEL_ID` | — | Model identifier (e.g. `gpt-4o`, `claude-sonnet-4-5`, `llama3.2`) |
| `DRY_RUN` | `false` | Skip LLM calls and infra; return canned fixtures |
| `POI_REPEATS` | `5` | Repeats per framework × scenario; scores are medians |
| `POI_PARALLEL` | `5` | Concurrent frameworks (each in its own venv subprocess) |
| `POI_RLC_MAX_CALLS` | `100` | Tool-call ceiling before the harness kills a runaway loop |
| `POI_RLC_CONFIGURED_LIMIT` | `5` | Limit used in the second RLC trial |
| `POI_AHQ_PAUSE_S` | `20` | Seconds the approval waits in RabbitMQ while no agent exists |
| `KUBE_CONTEXT` | `orbstack` | Kubernetes context for `./infra.sh` |

---

## 4. Baseline Scenarios

Baseline scenarios establish that each framework can express a realistic workflow before stressing its operability properties. They run in both `fixed` (identical DAG across all frameworks) and `idiomatic` (each framework's native patterns) form.

### GEW — Global Enterprise Workflow

A 5-step enterprise approval chain: account lookup → risk assessment → compliance check → CRM update → notification dispatch. Every step calls a distinct mock service via MCP.

**What it validates:** the framework can express a sequential workflow with external tool calls, and produces a checkpoint-capable graph (used by P1 probes for resume testing). The CRM update step is the idempotency probe: under concurrent resume, it must execute exactly once.

**Implementations:** `scenarios/gew/implementations/{langgraph,ms_agent,openai_agents_sdk,google_adk,strands_agents}/`

### TCW — Telco Next-Best-Action Workflow

A 5-step customer retention pipeline: profile fetch → Neo4j graph query → propensity model → channel selection → offer dispatch. The customer graph is a real Neo4j instance with populated data.

**What it validates:** the framework can handle a heterogeneous tool mix (REST, graph DB, ML API) and a stateful context that grows with each step. TCW's tool failure profile drives P2 and P3 evidence collection.

**Implementations:** `scenarios/tcw/implementations/{langgraph,ms_agent,openai_agents_sdk,google_adk,strands_agents}/`

---

## 5. Testing Principles

### Empirical over static

86 of the 99 model fields across all nine pillars are **probed at runtime** — the harness runs a workflow, kills a process, reads Jaeger spans, or counts lines between `# poi:custom-begin` / `# poi:custom-end` markers. Scores come from what the framework *did*, not from what its documentation claims.

The 13 remaining static fields require human judgment that cannot be automated (e.g. template creation hours, vendor independence assessment, ecosystem community score). See the breakdown below:

| Pillar | Empirical | Static | Static fields |
|--------|-----------|--------|---------------|
| P1 Durable Execution | 10/11 | 1 | `manual_watchdog_required` |
| P2 Blast-Radius | 15/16 | 1 | `custom_code_lines_for_isolation`* |
| P3 Observability | 10/12 | 2 | `proprietary_backend_required`, `alert_latency_ms` |
| P4 Packageability | 10/16 | 6 | `template_creation_time_hrs`, `deployment_time_hrs`, `one_day_deployment_achieved`, `blockers_encountered`, `framework_specific_hacks_required`, `required_framework_internal_hooks` |
| P5 Migration Fragility | 9/9 | 0 | — |
| P6 Tool Quality | 7/8 | 1 | `context_injection` |
| P7 Dev Experience | 11/13 | 2 | `community_score`, `vendor_independence_score` |
| P8 Security | 8/8 | 0 | — |
| P9 Ops Experience | 6/6 | 0 | — |

\* The P2 fallback hardcodes 5 lines; the SMA measured path counts isolation LOC from `isolation_shim.py` via `custom_loc.count()`.

### Ordinal 0–3, not continuous

We use a 0–3 ordinal scale per pillar because the differences that matter in practice are categorical. Whether LangGraph's resume latency is 280ms or 310ms is not what determines framework selection — whether it *has* resume at all is. Continuous scoring implies false precision.

### Live LLM, repeated, median, weakest link

All measured scenarios run against a live LLM (AI Refinery, `openai/gpt-oss-120b`, the same model for every framework). Each framework × scenario is run **5 times**:

- **Within a scenario:** the pillar score is the **median** of the repeats (lower median, so scores stay whole numbers). The range is reported next to it.
- **Across scenarios:** a pillar takes the **minimum**. Operability fails at its weakest link.
- **Inconclusive, not zero:** if the model stops calling the tool before any limit is reached, that repeat produces no evidence. It is excluded from the median and counted separately.

### The harness is the platform

The harness occupies the position a platform team occupies — outside the framework, acting only through signals a platform can send: a global OTel provider, a SIGKILL, a RabbitMQ message. It uses **SIGKILL, not SIGTERM**, because a graceful shutdown would let the framework flush state and flatter its durability score. The backing services are real: Postgres, RabbitMQ, Jaeger, and Neo4j — all on Kubernetes. Every tool call is appended to a per-run JSONL ledger that survives the kill.

### Operability Tax (OT-LOC)

OT-LOC is the sum of custom lines across P1–P4:

- **P1:** custom persistence code the framework doesn't provide
- **P2:** kill-switch or loop-budget glue code
- **P3:** custom telemetry exporter lines beyond the standard OTel setup
- **P4:** Helm template lines (all templates are operability overhead)

Lines are counted from `# poi:custom-begin` / `# poi:custom-end` markers in each implementation. No estimate or self-reported time feeds any score.

---

## 6. Scenario Deep Dives

### RLC — ReAct Loop Containment *(P2)*

**What it tests:** does the framework stop a runaway tool-calling loop without operator intervention, and does it surface a typed signal the platform can catch?

**How it runs:**
1. A ReAct agent is given a tool (`check_progress`) that always returns `"incomplete, retry"` — it never satisfies the agent's goal.
2. **Trial A (default settings):** the harness watches the tool ledger. If the framework stops the loop, the stop signal (exception class or typed stop reason) is recorded. If the loop reaches `POI_RLC_MAX_CALLS` (default 100), the harness sends SIGKILL — the framework failed to contain by default.
3. **Trial B (configured limit):** the framework's documented loop-limit setting is set to `POI_RLC_CONFIGURED_LIMIT` (default 5). The harness checks the limit is honoured.

**Evidence read:** tool call count, stop signal type, `configured_limit_honored`.

---

### SMA — Supervisor Multi-Agent *(P2, P3)*

**What it tests:** fault isolation (one specialist failing must not crash the run); OTel trace quality across agent hops.

**How it runs:**
1. A supervisor delegates to three specialists: billing, network, and retention — each wrapping a different tool.
2. **Trial A (healthy):** the run completes normally. The harness reads back spans from Jaeger (or in-process span buffers) and checks Gen-AI semantic-convention attributes, trace connectivity, and orphan spans.
3. **Trial B (fault injection):** the network specialist's tool raises an exception. The harness records whether the failure stayed contained, crashed the run, or hung it.
4. **Trial C (multi-tenancy):** three concurrent in-process invocations of the PORT isolation workflow check for cross-invocation state contamination.

**Evidence read:** `failure_propagation`, `sibling_agents_completed`, `concurrent_tenancy_safe`, `framework_spans`, `trace_ids_per_run`, `orphan_spans`, `alert_fired_without_custom_code`, `custom_exporter_loc`.

---

### AHQ — Async Human Approval *(P1)*

**What it tests:** does a paused approval survive a hard process kill and resume exactly once?

**How it runs:**
1. An agent runs until it hits the framework's human-approval gate (e.g. LangGraph `interrupt()`, a custom `await_approval()` stub for others). The process is then **SIGKILLed** — not SIGTERM.
2. The approval request is published to RabbitMQ. It sits there for `POI_AHQ_PAUSE_S` seconds while no agent process exists.
3. Two fresh processes receive the approval simultaneously (simulating at-least-once queue delivery). The harness checks: did the irreversible action execute exactly once, or twice?
4. `resume_succeeded`, `state_intact_after_kill`, and `side_effect_executions` are read from the ledger.

**Evidence read:** `resume_succeeded`, `state_intact_after_kill`, `steps_re_executed_on_resume`, `side_effect_executions`, `concurrent_resume_collision`, `resume_latency_ms`, `custom_code_lines_to_reach_score_3`.

---

### PORT — Tool Portability *(P6)*

**What it tests:** can the framework accept plain Python functions as tools without a framework decorator? Can it resume from a neutral conversation history? How many lines change when porting a workflow from another framework?

**How it runs:**
1. **tools_raw sub-test:** plain Python functions (no `@tool`, `function_tool()`, or `@tool` decorator) are passed to the framework's agent constructor. The ledger records which tools were actually called.
2. **switch sub-test:** decorator-wrapped tools are used, the agent completes a 3-step task. The output is checked for JSON-serializability.
3. **context sub-test:** a neutral conversation history (framework-agnostic dict) is injected as context; the agent is asked to continue from it.
4. **cross_venv sub-test:** the 20 SMA workflows ported from each source framework are run in each target framework's venv (with loop-limit isolation shims added); the success rate is recorded.

**Evidence read:** `tools_called_unmodified`, `task_completed`, `state_json_safe`, `context_portable`, `context_injection`, `port_changed_lines`, `cross_venv_success_rate`.

---

### DX — Developer Experience *(P7)*

**What it tests:** how quickly can a developer get a first run? How clear are error messages? Can the framework be observed and extended without class changes?

**How it runs:**
1. **TTR probe:** a smoke workflow is timed from cold import to first agent response.
2. **Error clarity probes (A–E):** five intentional mistakes are introduced one at a time (wrong return type, missing arg, bad LLM init, `None` instead of `str`, wrong type annotation). Each error's traceback is scored 0–3 on actionability.
3. **middleware_injectable:** a callback is registered without subclassing or patching the agent; tool invocations are checked against the ledger.
4. **local_testability:** the smoke workflow is run with no cloud credentials set; the resulting error is scored on clarity.
5. **escape_hatch:** custom OTEL endpoint, env-var overrides, and tracing configuration are tested without framework internals.

**Evidence read:** `time_to_first_run_s`, `error_clarity_a`–`e`, `functional_verified`, `middleware_injectable`, `local_testability_score`, `escape_hatch_score`, `community_score`, `vendor_independence_score`.

---

### SEC — Security Enforcement *(P8)*

**What it tests:** does the framework enforce security boundaries at the framework level, independent of LLM behaviour?

**How it runs:**
1. **scope sub-test:** `user_agent` has only `public_tool`. It is instructed to call `restricted_tool`. The harness checks whether the call was blocked by the framework.
2. **context sub-test:** `agent_a` retrieves PII. A fresh `agent_b` is started in a separate session. The harness checks whether the PII sentinel appears in `agent_b`'s output or context.
3. **telemetry sub-test:** a minimal agent runs with `POI_SEC_SENTINEL` embedded in the environment. Stdout/stderr are scanned for the sentinel value.
4. **bleed sub-test:** an agent is asked to fetch `POI_BLEED_TOKEN` from the environment and call an external API with it. A mock auth server logs any requests that carry the token.
5. **span_hygiene sub-test:** an LLM call runs with OTEL enabled. Jaeger spans are checked for raw HTTP LLM spans that lack Gen-AI semantic-convention attributes.

**Evidence read:** `tool_scope_enforced`, `context_isolation_verified`, `telemetry_clean`, `http_cred_bleed_events`, `trace_spans_clean`, `k8s_scope_enforced`, `admission_blocked`.

---

### OPS — Ops Experience *(P9)*

**What it tests:** token cost, latency, concurrency throughput, and resource footprint of a representative agent cycle. Whether checkpoint state survives a worker kill (cross-worker resume, wired from AHQ result).

**How it runs:**
1. **Primary run:** the DX SMOKE workflow is run as a child subprocess. A background thread samples child RSS and CPU via `psutil` at 0.5 s intervals throughout the run.
2. **Sequential baseline:** a single run is timed (wall-clock).
3. **Concurrent run:** `POI_OPS_CONCURRENCY` (default 3) runs are launched simultaneously via `ThreadPoolExecutor`. Throughput ratio = (N × sequential wall time) / concurrent wall time.
4. **cross_worker_resume:** read from the in-process `result_cache` populated by the AHQ trial (if AHQ ran in the same process). If AHQ has not run, the field stays `None`.

**Evidence read:** `input_tokens_per_run`, `agent_run_latency_ms`, `concurrent_throughput_ratio`, `peak_rss_mb`, `avg_cpu_percent`, `cross_worker_resume`.

---

## Results

### Score Matrix

| Framework | P1 | P2 | P3 | P4 | P5 | **POI (P1–P5)** |
|-----------|----|----|----|----|----|----|
| LangGraph (F1) | 2 | **3** | 1 | 2 | 1 | **9** |
| AutoGen/MS (F2) | 0 | 1 | 1 | 2 | 1 | **5** |
| OpenAI SDK (F3) | 0 | 1 | 1 | 2 | **3** | **7** |
| Google ADK (F4) | 2 | 1 | 1 | 2 | 2 | **8** |
| Strands (F5) | 0 | 1 | **2** | **3** | **3** | **9** |

### Operability Tax

| Framework | OT-LOC | POI |
|-----------|--------|-----|
| OpenAI SDK | 124 | 7 |
| AutoGen/MS | 135 | 5 |
| LangGraph | 179 | 9 |
| Strands | 195 | 9 |
| Google ADK | 221 | 8 |

### Per-Framework Findings

**LangGraph (POI 9, OT 179 LOC)**
- P2=3: the only framework with active runtime containment — `recursion_limit` is enforced by the graph executor, raising a structured `GraphRecursionError` catchable in application code.
- P1=2: resume works, but the checkpoint format is LangGraph-specific. Cross-process portability requires swapping to `PostgresSaver` — one config change, no code change, but still an operator step.
- P5=1: checkpoint schema changes across minor versions require migration.
- **The OT paradox:** highest POI, but 179 LOC of scaffolding is the checkpoint backend wiring and psycopg Dockerfile overhead — the price of its P1 capability.

**Strands (POI 9, OT 195 LOC)**
- P4=3: the only framework with zero framework-specific Kubernetes workarounds. OTel is configured via standard `OTEL_EXPORTER_OTLP_ENDPOINT`; secrets are standard env vars.
- P3=2: all four required Gen-AI OTel attributes emitted natively — but the `StrandsTelemetry` setup still requires 2 lines of operator code.
- P1=0: no native checkpoint/resume. A crash at step 4 means full restart from step 1.
- **Counterintuitive:** ties LangGraph at POI=9 via an entirely different profile — packaging and stability vs durability and containment.

**Google ADK (POI 8, OT 221 LOC)**
- P1=2: `InMemorySessionService` provides native checkpoint with a parseable JSON format and working resume — but only to GCP services, not portable to non-GCP infrastructure.
- P4=2: highest OT of any framework. Three mandatory environment variables are not standard K8s primitives and require framework-specific Helm annotations.
- **The cloud coupling cost:** designed for Cloud Run; Kubernetes deployment requires a LiteLLM routing layer and GCP-specific environment variables.

**OpenAI SDK (POI 7, OT 124 LOC)**
- P5=3: most stable changelog — 0.5 breaking changes per release on average, no checkpoint schema migrations.
- P1=0: checkpoint state is managed by OpenAI's backend. Resume works — but only if you trust OpenAI's persistence layer. The state is not inspectable, not portable, not under your control.
- **The OT paradox:** lowest OT (124 LOC) because it delegates checkpoint to a vendor backend — an operability trade-off, not a win.

**AutoGen/MS (POI 5, OT 135 LOC)**
- P1=0: `GroupChat` conversation state is in-memory only.
- P5=1: highest breaking-change frequency — 3.1 breaking changes per release on average.
- **The honest finding:** AutoGen's strength is multi-agent coordination patterns. Its weakness is everything that happens after those patterns are deployed.

---

## Ranking and Stability

### Equal-Weight Ranking

1. **LangGraph** — POI 9, OT 179 LOC
2. **Strands** — POI 9, OT 195 LOC
3. **Google ADK** — POI 8, OT 221 LOC
4. **OpenAI SDK** — POI 7, OT 124 LOC
5. **AutoGen/MS** — POI 5, OT 135 LOC

### Sensitivity Analysis

POI re-ran the ranking under 1,000 weight vectors drawn from a Dirichlet(α=1) distribution — uniform sampling over all possible ways to weight five pillars.

| Pairwise comparison | Holds under | Interpretation |
|---------------------|-------------|----------------|
| LangGraph > Strands | 48% of draws | **Fragile.** Effectively a coin flip — the POI=9 tie reflects genuine closeness. |
| Strands > Google ADK | 71% of draws | Contested. Strands' packaging and stability advantage is partly offset by ADK's checkpoint lead. |
| Google ADK > OpenAI SDK | 67% of draws | Contested. Sensitive to how heavily P1 vs P5 is weighted. |
| OpenAI SDK > AutoGen | 100% of draws | **Stable.** AutoGen trails all others regardless of pillar weighting. |

**Full ranking unchanged in 15% of draws.** The only result you can state with confidence is that AutoGen trails the field. Treat rankings #1–#4 as directional signals, not definitive orderings.

---

## What This Benchmark Does Not Tell You

**It does not measure capability.** POI says nothing about reasoning quality, task success rate, or tool-use accuracy. Pair POI with a capability benchmark (GAIA, SWE-bench) for a complete picture.

**It does not measure cost.** LLM API costs, token efficiency, and inference latency are not pillar inputs.

**n=1 implementation.** Each framework is implemented once per scenario. Scores reflect one team's interpretation of each framework's idiomatic patterns.

---

## License

Private research benchmark. All rights reserved.
