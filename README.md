# Platform Operability Index (POI)

**Agent Frameworks Benchmarking — Principles and Rationale**

A reproducible benchmark for measuring the **production operability** of five Python agentic frameworks across two enterprise workflow scenarios.

---

## The Problem

Most agentic framework evaluations stop at capability: can it reason, can it use tools, does it pass the task? That is the wrong question for an enterprise platform team.

The question that matters in production is: **what does the framework cost to operate at scale?**

A framework that scores well on capability benchmarks but lacks native checkpointing will force your platform team to write custom crash-recovery wrappers. One that emits no OpenTelemetry spans means your SRE team flies blind when an agent loop misbehaves at 2am. One that ships breaking API changes on patch releases turns every quarterly upgrade into a multi-team coordination event.

These costs are real, recurring, and rarely measured. They compound: a team that spends two weeks writing checkpoint scaffolding is also the team that falls behind on feature delivery, delays the next framework upgrade, and accumulates technical debt that future teams inherit.

**POI quantifies that cost as two numbers:**
- **POI score (0–15):** how much the framework provides out of the box. Higher = less work for your platform team.
- **OT-LOC (Operability Tax, lines of code):** how much custom scaffolding your team must write to reach production-grade operability. Lower = less ongoing maintenance burden.

---

## Why These Five Pillars

The five pillars were selected from the failure modes most commonly cited in enterprise post-mortems for agentic systems:

### P1 — Durable Execution & Replayability
**The failure mode:** an agent crashes at step 4 of 7. Without checkpointing, the entire workflow replays from step 1 — re-running external API calls, retrying CRM writes, re-triggering approvals. With idempotency gaps, retried calls cause duplicate side effects.

**What we measure (AHQ scenario):** an agent pauses at the framework's own human-approval gate before an irreversible action. The harness SIGKILLs the process, sends the approval through RabbitMQ while no agent process exists, then delivers it twice (at-least-once, as queues do) to two fresh processes resuming at the same instant. Does the run resume with its state intact, without re-running earlier steps, and does the irreversible action execute exactly once? How much custom persistence code did it take?

**Why this matters at scale:** at 10,000 agent runs/day, even a 1% crash rate means 100 full workflow replays daily. At step-level restart, that's a 7× reduction in wasted compute and external API calls.

### P2 — Blast-Radius Containment
**The failure mode:** a prompt injection or model hallucination triggers an infinite tool-calling loop. Without native containment, the loop runs until it exhausts API credits, fills a database, or is killed by ops after a page.

**What we measure (RLC and SMA scenarios):** in RLC, a ReAct agent is given a tool that never returns what it asks for. Does the framework stop the loop *with its default settings*, and does it surface a typed signal (an exception class or typed stop reason) the platform can catch? If not, the harness — acting as the platform — kills the process at a tool-call ceiling. A second trial sets the framework's documented limit and checks it is honoured. In SMA, one specialist agent's tool fails: does the failure stay inside that agent, or does it crash or hang the whole multi-agent run?

**Why this matters at scale:** a runaway loop in a shared multi-tenant environment is a cross-tenant incident. Native containment means the framework handles this without operator intervention; SIGTERM-only containment means a human must be paged.

### P3 — Observability Nativeness
**The failure mode:** an agent loop fails intermittently. Your SRE team checks Grafana and finds no spans, no token counts, no latency histograms — because the framework emits no OpenTelemetry data by default. Root-cause analysis requires log archaeology.

**What we measure (SMA scenario):** the harness installs the standard platform OTel setup — a global TracerProvider exporting OTLP to Jaeger — and nothing framework-specific. After a supervisor delegates to three specialists, the run's spans are read back from Jaeger. Do they carry the Gen-AI semantic-convention attributes (`gen_ai.operation.name`, `gen_ai.provider.name` or its predecessor `gen_ai.system`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`)? Is the whole multi-agent run one connected trace, with every agent visible and no orphaned spans?

**Why this matters at scale:** a framework that requires a custom OTel exporter means one more piece of infrastructure your platform team owns, maintains, and on-calls for.

### P4 — Golden-Path Packageability
**The failure mode:** deploying the framework to a policy-enforced Kubernetes cluster requires undocumented environment variables, framework-internal hooks, or template hacks that bypass Kyverno ClusterPolicies. Every deployment is a one-off negotiation with the security team.

**What we measure:** can the framework be packaged as a Helm chart in ≤ 200 lines that passes a standard set of Kyverno policies (secrets via `secretKeyRef`, resource limits declared, OTel endpoint configured) without framework-specific workarounds?

**Why this matters at scale:** organisations with dozens of agent services need a golden-path chart that any team can copy-paste. Framework-specific hacks mean the chart cannot be standardised — each team maintains its own fork.

### P5 — Day-2 Migration Fragility
**The failure mode:** a patch-level framework upgrade ships a renamed method, a changed tool schema, or a new checkpoint format. Agents that were working break silently; or worse, resume from checkpoints that are now unreadable.

**What we measure:** how many breaking changes (API, schema, prompt) appear per release on average? Does a checkpoint migration step appear in the upgrade guide? Is the changelog explicit and machine-parseable?

**Why this matters at scale:** at 50 agent services across 10 teams, a framework with 3 breaking changes per release means 150 code changes on every quarterly upgrade cycle — across teams, across environments, requiring co-ordinated freeze windows.

---

## The Measurement Philosophy

### Ordinal 0–3 scale, not continuous

We use a 0–3 ordinal scale per pillar because the differences that matter in practice are categorical:
- Score 0: the property is absent — you must build it from scratch.
- Score 1: the property exists but requires significant custom scaffolding.
- Score 2: the property works but with manual operator configuration.
- Score 3: the property is fully native — the framework handles it without custom code.

Continuous scoring would imply false precision. Whether LangGraph's resume latency is 280ms or 310ms is not what determines framework selection — whether it *has* resume at all is.

### Measure behaviour, don't describe it

An operability benchmark earns credibility only if its scores come from what the framework *did*, not from what its documentation says. POI v1 scored durability, containment and observability largely from desk research, and several of those values turned out to be wrong once measured. For example, LangGraph's default recursion limit is 10,007 steps, not 25, and two frameworks re-raise a specialist agent's tool exception and crash the whole run.

POI therefore separates two kinds of scenario.

**Measured scenarios — the evidence for P1–P3.** Each one is built to stress a specific pillar. All are idiomatic: they exist to exercise each framework's *native* mechanism, so a lowest-common-denominator version would defeat the purpose.

| Scenario | Stresses | What the harness does |
|---|---|---|
| **RLC** — ReAct loop containment | P2 | Gives a ReAct agent a tool that always answers "incomplete, call again"; kills the process at a tool-call ceiling if the framework doesn't stop it; repeats with the documented limit set |
| **SMA** — supervisor multi-agent | P2, P3 | A supervisor delegates to billing, network and retention specialists (agents-as-tools). Reads the healthy run's spans back from Jaeger; then makes the network specialist's tool fail |
| **AHQ** — async human approval | P1 | Pauses at the framework's approval gate, SIGKILLs the process, routes the approval through RabbitMQ, resumes in two fresh processes simultaneously |

**Baseline workflows — GEW and TCW.** A 5-step enterprise approval chain and a 5-step telco next-best-action pipeline, each implemented in a fixed (identical DAG) and an idiomatic form. They check that each framework can express a realistic workflow, and they carry the P4 and P5 inputs, which are framework properties that don't depend on the scenario. TCW's customer graph is a real Neo4j database.

### The harness is the platform

The measured scenarios put the harness in the position a platform team occupies. It supervises each trial as a separate process and does only what a platform can do from outside: set a global OTel provider, kill a runaway process, route messages through a queue. It uses **SIGKILL, not SIGTERM**, because a graceful shutdown would let the framework flush its state and flatter its durability score. The backing services are real: Postgres (checkpoints), RabbitMQ (approvals), Jaeger in the Istio mesh (traces) and Neo4j (customer graph), all on the same Kubernetes cluster. Every tool call is written to an append-only ledger that survives the kill, and the evidence is read from that ledger rather than from what the framework reports about itself.

### Live LLM, repeated, median, weakest link

All measured scenarios run against a live LLM (AI Refinery, `openai/gpt-oss-120b`, the same model for every framework). A live model varies from run to run, so each framework × scenario is run **5 times**:
- **Within a scenario**, the pillar score is the **median** of the repeats (the lower median, so scores stay whole numbers). The range is reported next to it.
- **Across scenarios**, a pillar takes the **minimum**. Operability fails at its weakest link, so a framework that contains runaway loops but crashes when one agent fails does not get credit for containment.
- **Inconclusive, not zero.** If the model stops calling the tool before any limit is reached, that RLC repeat produces no evidence. It is excluded from the median and counted separately. A framework is never scored on a test that didn't actually happen.

### Operability Tax (OT-LOC) as a second axis

POI score tells you what the framework gives you. OT-LOC tells you what you pay for what it doesn't give you. A framework with POI=7 and OT=124 LOC may be more practical than one with POI=9 and OT=179 LOC, depending on your team's capacity to maintain scaffolding.

OT-LOC is the sum of custom lines needed across P1–P4:
- P1: custom persistence the framework doesn't provide (for example, storing serialised run state in Postgres)
- P2: kill-switch or loop-budget glue code
- P3: custom telemetry glue beyond the standard global OTel setup
- P4: Helm template lines (all templates are operability overhead — a framework with a leaner packaging footprint requires less YAML to maintain)

Custom code is fenced in the implementations with `# poi:custom-begin` / `# poi:custom-end` markers, and the harness counts the fenced lines. Helm templates are counted directly. No estimate or self-reported time feeds any score.

---

## The Five Pillars — Scoring Rubric

| Pillar | Score 0 | Score 1 | Score 2 | Score 3 |
|---|---|---|---|---|
| **P1 Durable Execution** (AHQ) | Cannot resume in a fresh process after SIGKILL | Resumes, but state is lost or earlier steps re-run | Resumes cleanly, but needs custom persistence code **or** executes the irreversible action twice under concurrent resume | Resumes cleanly from a native durable backend, zero custom code, action executes exactly once |
| **P2 Blast-Radius** (RLC, SMA) | A failing agent hangs the whole run | Only a platform kill stops a runaway loop; **or** one failing agent crashes the whole run | Loop stops only once a limit is configured, or stops by default without a typed signal | Stops a runaway loop by default with a typed exception or stop reason, **and** a failing agent stays contained |
| **P3 Observability** (SMA) | No OTel spans reach the collector | Spans lack required Gen-AI attributes | All attributes present, but the multi-agent run is not one connected trace, or custom telemetry code was needed | All attributes, one connected trace covering every agent, no custom code |
| **P4 Packageability** | No Helm path | > 200 template lines | ≤ 200 lines, framework-specific K8s workarounds | ≤ 200 lines, zero workarounds, standard K8s primitives only |
| **P5 Migration Fragility** | > 3 breaking changes/release avg | 1–3 breaking changes/release avg | < 1 breaking change/release, no schema migration | Zero breaking changes in patch; stable checkpoint schema |

---

## Frameworks Benchmarked

| ID | Framework | What it is |
|---|---|---|
| F1 | [LangGraph](https://github.com/langchain-ai/langgraph) | Graph-based stateful agent orchestration by LangChain |
| F2 | [AutoGen / MS AgentChat](https://github.com/microsoft/autogen) | Microsoft's multi-agent conversation framework |
| F3 | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | OpenAI's first-party agent SDK with hosted state |
| F4 | [Google ADK](https://github.com/google/adk-python) | Google's Agent Development Kit, Cloud Run-native |
| F5 | [Strands Agents](https://github.com/strands-agents/sdk-python) | AWS-backed lightweight agent framework |

---

## Results

### Score Matrix

| Framework | P1 | P2 | P3 | P4 | P5 | **POI** |
|---|---|---|---|---|---|---|
| LangGraph (F1) | 2 | **3** | 1 | 2 | 1 | **9** |
| AutoGen/MS (F2) | 0 | 1 | 1 | 2 | 1 | 5 |
| OpenAI SDK (F3) | 0 | 1 | 1 | 2 | **3** | 7 |
| Google ADK (F4) | 2 | 1 | 1 | 2 | 2 | 8 |
| Strands (F5) | 0 | 1 | **2** | **3** | **3** | **9** |

### Operability Tax

| Framework | OT-LOC | POI |
|---|---|---|
| OpenAI SDK | 124 | 7 |
| AutoGen/MS | 135 | 5 |
| LangGraph | 179 | 9 |
| Strands | 195 | 9 |
| Google ADK | 221 | 8 |

### Per-Framework Findings

**LangGraph (POI 9, OT 179 LOC)**
- P2=3: the only framework with *active* runtime containment — `recursion_limit` is enforced by the graph executor, which raises a structured `GraphRecursionError` catchable in application code. Every other framework either requires custom loop logic or relies on SIGTERM.
- P1=2 (not 3): MemorySaver checkpoints are parseable and resume works, but the checkpoint format is LangGraph-specific. Cross-process portability requires swapping to PostgresSaver — one config change, no code change, but still an operator step. Score-3 requires zero operator steps.
- P5=1: checkpoint schema changes across minor versions require migration. The upgrade guide documents these, but they still require coordinated deploys.
- **The OT paradox:** LangGraph has the highest POI but its 179 LOC of scaffolding is the checkpoint backend wiring and psycopg Dockerfile overhead — the price of its P1 capability.

**Strands (POI 9, OT 195 LOC)**
- P4=3: the only framework with zero framework-specific Kubernetes workarounds. OTel is configured via standard `OTEL_EXPORTER_OTLP_ENDPOINT`; secrets are standard env vars. The Helm chart passes all Kyverno ClusterPolicies without hacks.
- P3=2 (not 3): Strands emits all four required Gen-AI OTel attributes natively — but still requires `strands-otel` to be wired up as a custom exporter. The attributes are there; the plumbing isn't automatic.
- P1=0: no native checkpoint/resume mechanism. A crash at step 4 means full restart from step 1. Reaching score-3 P1 requires a custom state-serialisation wrapper (~80 LOC), which is the primary driver of its OT.
- **The counterintuitive result:** Strands ties LangGraph at POI=9 via an entirely different profile — it wins on packaging and API stability where LangGraph wins on durability and containment.

**Google ADK (POI 8, OT 221 LOC)**
- P1=2: `InMemorySessionService` provides native checkpoint with a parseable JSON format and working resume. The session backend is swappable (Cloud Firestore, Vertex AI) — but only to GCP services, not portable to non-GCP infrastructure.
- P4=2: the highest OT of any framework. Three mandatory environment variables (`ADK_RUNNER`, `GOOGLE_CLOUD_PROJECT`, `LITELLM_BASE_URL`) are not standard K8s primitives — they require framework-specific Helm template annotations and Kyverno policy exceptions.
- **The cloud coupling cost:** ADK is designed for Cloud Run. Deploying to generic Kubernetes requires a LiteLLM routing layer and environment variables that reveal the framework's GCP assumptions, adding scaffolding other frameworks don't need.

**OpenAI SDK (POI 7, OT 124 LOC)**
- P5=3: the most stable changelog of the five frameworks — 0.5 breaking changes per release on average, no checkpoint schema migrations. The lowest upgrade friction by a wide margin.
- P1=0: checkpoint state is managed by OpenAI's backend, not by your infrastructure. Resume works — but only if you trust OpenAI's persistence layer and accept vendor lock-in. The state is not inspectable, not portable, not under your control.
- **The OT paradox:** lowest OT (124 LOC) with POI=7. The low OT comes from not needing checkpoint scaffolding — because the framework delegates checkpoint to a vendor backend. This is an operability trade-off, not a win: you trade LOC for control.

**AutoGen/MS (POI 5, OT 135 LOC)**
- P1=0: no native checkpoint/resume. The GroupChat conversation state is in-memory only.
- P5=1: highest breaking-change frequency of the five frameworks — 3.1 breaking changes per release on average. The v0.2 → v0.4 transition renamed core APIs and changed agent configuration schemas.
- **The honest finding:** AutoGen's strength is multi-agent coordination patterns (`RoundRobinGroupChat`, `SelectorGroupChat`). Its weakness is everything that happens after those patterns are deployed. For teams that need durable, observable, stable agent infrastructure, it requires the most scaffolding for the least native support.

---

## Ranking and Stability

### Equal-Weight Ranking

Ranking primary: POI score descending. Tiebreak: OT-LOC ascending (less scaffolding burden wins).

1. **LangGraph** — POI 9, OT 179 LOC
2. **Strands** — POI 9, OT 195 LOC
3. **Google ADK** — POI 8, OT 221 LOC
4. **OpenAI SDK** — POI 7, OT 124 LOC
5. **AutoGen/MS** — POI 5, OT 135 LOC

### Sensitivity Analysis

Equal pillar weights are an assumption. POI re-ran the ranking under 1,000 weight vectors drawn from a Dirichlet(α=1) distribution — uniform sampling over all possible ways to weight five pillars.

| Pairwise comparison | Holds under | Interpretation |
|---|---|---|
| LangGraph > Strands | 48% of draws | **Fragile.** Effectively a coin flip — the POI=9 tie reflects genuine closeness, not a clear winner. |
| Strands > Google ADK | 71% of draws | Contested. Strands' packaging and API stability advantage is partly offset by ADK's checkpoint lead. |
| Google ADK > OpenAI SDK | 67% of draws | Contested. Sensitive to how heavily P1 (durability) vs P5 (stability) is weighted. |
| OpenAI SDK > AutoGen | 100% of draws | **Stable.** AutoGen trails all others regardless of how the pillars are weighted. |

**Full ranking unchanged in 15% of draws.**

The honest conclusion: the only result you can state with confidence is that AutoGen trails the field. The LangGraph #1 position is a tiebreak artifact that reverses under many reasonable weight assumptions. Treat rankings #1–#4 as directional signals, not definitive orderings.

---

## What This Benchmark Does Not Tell You

**It does not measure capability.** POI says nothing about reasoning quality, task success rate, or tool-use accuracy. A framework with POI=9 can still produce wrong answers. Pair POI with a capability benchmark (e.g., GAIA, SWE-bench) for a complete picture.

**It does not measure cost.** LLM API costs, token efficiency, and inference latency are not pillar inputs. A framework that batches tool calls efficiently may be cheaper to run than one that serialises them, independent of POI score.

**P3 and P5 are partially desk research.** P3 observability scores are based on documented OTel integration status and attribute completeness checks; they are not based on live trace capture. P5 migration fragility is based on changelog analysis, not on running actual upgrade scripts. Both are reproducible (the changelogs are public) but are subject to interpretation.

**DRY_RUN mode.** All 20 benchmark combinations (5 frameworks × 2 scenarios × 2 implementation types) were run with `DRY_RUN=true` — workflows return canned fixtures without LLM calls or external service calls. P1 timing measurements (resume latency, duplicate call counts) require live runs with real infrastructure to be precise.

**n=1 implementation.** Each framework is implemented once per scenario and implementation type. Scores reflect one team's interpretation of each framework's idiomatic patterns. A different implementer might make different choices that produce different OT-LOC counts.

---

## Reproducibility

The full benchmark is open at [github.com/ketan1602/platform-operability-index](https://github.com/ketan1602/platform-operability-index) (private during review period).

To reproduce the score matrix and sensitivity analysis:

```bash
git clone <repo>
pip install pydantic pyyaml structlog requests
DRY_RUN=true python3 -m harness.run_all
python3 analysis/poi_report.py
```

---

## License

Private research benchmark. All rights reserved.
