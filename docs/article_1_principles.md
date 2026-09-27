# Agent Frameworks Benchmarking — Principles and Rationale

*Article 1 of 2. Article 2 applies this framework to five specific frameworks and publishes the results.*

---

## The Problem with How We Evaluate Agentic Frameworks Today

When an engineering team evaluates a new agentic framework, they typically run it through a capability benchmark: does it complete the task, how many steps does it take, does it use tools correctly? These are the right questions for a research demo. They are the wrong questions for a team that will run this framework at scale in production.

The capability question is: *can this framework reason about my problem?*

The operability question is: *what happens six months after we ship it?*

Enterprise platform teams inherit the operability properties of whatever framework they choose — good and bad. A framework that lacks native checkpointing forces your team to write custom crash-recovery wrappers. One that emits no OpenTelemetry spans means your SREs fly blind when an agent loop misbehaves at 2am. One that ships breaking API changes on patch releases turns every quarterly upgrade into a multi-team coordination event.

These costs are real, recurring, and compound. A team that spends two weeks building checkpoint scaffolding for one framework cannot spend those two weeks on features. When the next framework release ships a renamed method, they spend another week on migration. Meanwhile, the capability benchmark still shows a score of 87%.

**The Platform Operability Index (POI)** is a benchmarking framework designed to measure these post-ship costs before you commit to a framework.

---

## What We Measure and Why

POI is structured around five operational failure modes drawn from enterprise post-mortems for agentic systems. Each failure mode becomes a **pillar** — a named, scored dimension of operability.

```
┌─────────────────────────────────────────────────────────────────┐
│                   Five Operability Pillars                       │
├──────┬─────────────────────────────┬────────────────────────────┤
│  P1  │ Durable Execution           │ Crash at step 4 of 7.      │
│      │ & Replayability             │ What restarts?             │
├──────┼─────────────────────────────┼────────────────────────────┤
│  P2  │ Blast-Radius Containment    │ Runaway loop at 2am.       │
│      │                             │ What stops it?             │
├──────┼─────────────────────────────┼────────────────────────────┤
│  P3  │ Observability Nativeness    │ Agent fails intermittently. │
│      │                             │ Where are the spans?       │
├──────┼─────────────────────────────┼────────────────────────────┤
│  P4  │ Golden-Path Packageability  │ Deploy to K8s.             │
│      │                             │ How many policy hacks?     │
├──────┼─────────────────────────────┼────────────────────────────┤
│  P5  │ Day-2 Migration Fragility   │ Patch-level upgrade.       │
│      │                             │ How much breaks?           │
└──────┴─────────────────────────────┴────────────────────────────┘
```

Each pillar is scored **0–3**. The scale is ordinal, not continuous:

| Score | Meaning |
|---|---|
| 0 | The property is absent. Your team builds it from scratch. |
| 1 | The property exists but requires significant custom scaffolding. |
| 2 | The property works with manual operator configuration. |
| 3 | Fully native. The framework handles it without custom code. |

We use ordinal scoring because the differences that matter in practice are categorical. Whether LangGraph's resume latency is 280ms or 310ms does not drive a framework decision. Whether it *has resume at all* does.

The sum across pillars is the **POI score** (0–15). Higher is better — the framework provides more out of the box.

---

## How the Measurement Works

Every pillar score is derived from a measurement made against a running workflow, not from documentation claims or vendor marketing. The harness works as follows:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        POI Measurement Pipeline                       │
│                                                                        │
│  ┌─────────────┐    ┌──────────────────────────────────────────────┐  │
│  │  Scenarios  │    │              Harness Adapters                 │  │
│  │             │    │                                               │  │
│  │  GEW        │───▶│  Adapter F1 (LangGraph)                      │  │
│  │  5-step     │    │  Adapter F2 (AutoGen)          ┌──────────┐  │  │
│  │  approval   │    │  Adapter F3 (OpenAI SDK)  ────▶│  score   │  │  │
│  │  chain      │    │  Adapter F4 (Google ADK)       │  p1..p5  │  │  │
│  │             │    │  Adapter F5 (Strands)           └────┬─────┘  │  │
│  │  TCW        │───▶│                                       │        │  │
│  │  5-step     │    └───────────────────────────────────────┼───────┘  │
│  │  telco CVM  │                                            │           │
│  └─────────────┘    ┌──────────────────────────────────────▼───────┐  │
│                      │              Results per run                   │  │
│  ┌─────────────┐    │  framework_id, scenario, pillar_scores,       │  │
│  │  Mock Infra │    │  raw_measurements, operability_tax_loc        │  │
│  │             │    └──────────────────────────────────────────────┘  │
│  │  FastAPI    │                           │                           │
│  │  servers    │    ┌──────────────────────▼───────────────────────┐  │
│  │  DRY_RUN-   │    │            poi_report.py                      │  │
│  │  aware      │    │  Score matrix · OT-LOC table · Ranking        │  │
│  └─────────────┘    │  Sensitivity analysis (Dirichlet weights)     │  │
│                      └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**Key design choices in the harness:**

- **Subprocess isolation.** Each framework adapter runs in its own process with its own dependency set. This prevents library conflicts (different Pydantic versions, different OpenTelemetry SDKs) from contaminating results.
- **Two scenarios.** GEW (Generic Enterprise Workflow — a 5-step approval chain) and TCW (Telco CVM/NBA — a 5-step personalisation pipeline). Two scenarios because a single scenario risks optimising for one domain's patterns. Scores are framework properties, not scenario properties — a framework's checkpointing behavior is the same regardless of what the workflow does.
- **Fixed and idiomatic implementations.** Every scenario is implemented twice per framework: once with a linear DAG identical across all frameworks (apples-to-apples baseline), once using each framework's native patterns. If scores differ between fixed and idiomatic, it means the framework's idiomatic patterns impose operability trade-offs.
- **DRY_RUN mode.** Every workflow returns canned fixtures when `DRY_RUN=true`. The full benchmark reproduces with no LLM credentials, no external services. Scores are verifiable.

---

## A Second Axis: Operability Tax (OT-LOC)

The POI score tells you what the framework gives you. It does not tell you what you pay for what it doesn't give you.

**OT-LOC** (Operability Tax, measured in lines of code) captures that cost: how much custom scaffolding must your platform team write and maintain to reach production-grade operability?

OT-LOC is the sum of:
- Custom checkpoint/resume wrapper (P1 gap)
- Kill-switch or loop-budget glue code (P2 gap)
- Custom OTel exporter shim (P3 gap)
- Helm template lines (P4 — all templates are operability overhead)

A framework with POI=9 and OT=179 LOC is not strictly better than one with POI=7 and OT=124 LOC. The first gives you more natively; the second gives you less but requires less ongoing maintenance. Which is better depends on your team's capacity.

All OT-LOC inputs are counted by code or documented in source — no self-reported time estimates feed any score.

---

## Worked Example 1 — P1: Durable Execution

**The failure mode:** an agent workflow crashes at step 4 of 7. All four external API calls before step 4 have already executed. Without checkpointing, the entire workflow replays from step 1 — re-running those calls, duplicating CRM writes, re-triggering approvals. With checkpointing but no idempotency, step 4 runs again and creates a duplicate record.

**What the harness measures (T1–T5):**

```
T1  Run the baseline workflow end-to-end.
    → Does it complete all 5 steps?

T2  Interrupt mid-flight. Resume from checkpoint.
    → How many steps re-execute? (target: 0)
    → What is the resume latency?

T3  Simulate a mid-write crash. Re-run.
    → Are any tool calls duplicated? (target: 0)

T4  Inspect the checkpoint artefact.
    → Is the format human-readable / parseable, or opaque binary?

T5  Attempt concurrent resume from the same checkpoint.
    → Does the framework prevent a collision, or do two runs race?
```

**How measurements map to scores:**

| Observation | Score |
|---|---|
| No checkpoint mechanism; full replay on step 1 | 0 |
| Checkpoint exists but format is opaque (not inspectable by an operator) | 1 |
| Native checkpoint, parseable format, zero re-executions on resume | 2 |
| Portable checkpoint (cross-process, cross-node); concurrent-resume collision prevented | 3 |

**What differentiates score 2 from score 3:** score 3 requires the checkpoint to be portable — readable by a different process on a different node, without framework-specific deserialisation code. Score 2 means resume works but only within the same process or with framework-specific state. In practice: LangGraph's MemorySaver achieves score 2; switching to PostgresSaver makes it portable, but that requires an operator configuration step that costs one OT-LOC point.

---

## Worked Example 2 — P2: Blast-Radius Containment

**The failure mode:** a prompt injection or model hallucination triggers an infinite tool-calling loop. Without native containment, the agent calls the same tool hundreds of times, exhausting API credits, filling a database, or triggering rate-limit bans — until an operator pages and kills the process.

**What the harness measures (FI-3: Failure Injection 3):**

```python
# The test injects a loop trigger into the workflow state
# and measures what each framework does next

def inject_loop_trigger(state):
    return {"next_action": "LOOP_FOREVER"}

# Framework A (LangGraph):
#   → executor enforces recursion_limit
#   → raises GraphRecursionError after N steps
#   → error is catchable in application code
#   → time to halt: < 500ms
#   → result: score 3

# Framework B (AutoGen, OpenAI SDK, Google ADK, Strands):
#   → no native loop budget enforced by default
#   → loop runs until SIGTERM, resource exhaustion, or operator intervention
#   → result: score 1 (platform SIGTERM is the only mechanism)
```

**How measurements map to scores:**

| Observation | Score |
|---|---|
| No mechanism; loop runs unbounded | 0 |
| Platform SIGTERM is the only stop (requires ops intervention) | 1 |
| Configurable `max_iterations` / `recursion_limit` parameter exists | 2 |
| Framework catches runaway at runtime, surfaces a structured, catchable error | 3 |

**What differentiates score 2 from score 3:** score 2 means an operator *can* set a budget by passing a parameter; score 3 means the framework *enforces* the budget by default and surfaces it as a structured error your application code can handle — without requiring the operator to have set it explicitly. This distinction matters for multi-tenant platforms where individual agent configurations cannot be trusted.

**Why this is the most differentiating pillar:** across all five frameworks tested, only one achieves score 3 on P2. This single pillar accounts for a 2-point spread in the POI score — more differentiation than any other pillar. It is also the pillar least visible in capability benchmarks.

---

## The Scoring Assumption and Its Risk

POI scores are summed with equal pillar weights. Equal weights are an explicit assumption — they are not derived from data. Different platform teams weight these pillars differently: a team running long-horizon autonomous agents cares more about P1 (durability) than a team running short stateless pipelines; a team under strict compliance cares more about P2 (containment) than a team in a sandboxed internal environment.

To quantify the risk of the equal-weight assumption, the benchmark runs 1,000 weight vectors drawn from a Dirichlet distribution (uniform over all possible pillar weightings) and re-ranks all frameworks under each. The result is a **rank-stability table** published with the Article 2 findings.

The honest conclusion: rankings should be read as directional signals, not definitive orderings. The benchmark tells you which frameworks are categorically weak on which dimensions. It does not tell you which framework your team should choose — that depends on which pillars matter most to your context.

---

## What This Article Does Not Cover

Article 1 defines the measurement framework. It does not report results for specific frameworks.

Article 2 applies this framework to five production agentic frameworks — LangGraph, Microsoft AutoGen, OpenAI Agents SDK, Google ADK, and Amazon Bedrock / Strands — and publishes the complete score matrix, OT-LOC table, per-framework findings, and ranking stability analysis.

The full benchmark harness, all scenario implementations, Helm charts, and scoring code are published at the repository linked in Article 2.
