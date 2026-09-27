# Agent Frameworks Benchmarking — Results Across Five Frameworks

*Article 2 of 2. Article 1 defines the Platform Operability Index (POI) methodology: the five pillars, the measurement approach, and the scoring philosophy. This article applies it.*

**Frameworks covered:** LangGraph · Microsoft AutoGen (AgentChat) · OpenAI Agents SDK · Google ADK · Amazon Bedrock / Strands Agents

**Reproduce these results in < 5 minutes:**
```bash
git clone https://github.com/ketan1602/platform-operability-index
cd platform-operability-index
pip install pydantic pyyaml structlog requests
DRY_RUN=true python3 -m harness.run_all
python3 analysis/poi_report.py
```

---

## The Five Frameworks

| ID | Framework | What it is |
|---|---|---|
| F1 | **LangGraph** | Graph-based stateful agent orchestration by LangChain. Native checkpointing via MemorySaver / PostgresSaver. Python-first. |
| F2 | **Microsoft AutoGen (AgentChat)** | Microsoft's multi-agent conversation framework. GroupChat-based coordination. Strong multi-agent patterns. |
| F3 | **OpenAI Agents SDK** | OpenAI's first-party Python SDK. Hub-and-spoke handoffs. Checkpoint state is hosted on OpenAI's backend. |
| F4 | **Google ADK** | Google's Agent Development Kit. SequentialAgent / LlmAgent composition. Cloud Run-native; designed for GCP. |
| F5 | **Amazon Bedrock / Strands Agents** | Amazon's open-source agent SDK. Bedrock as the default LLM backend. Lightweight `@tool` decorator pattern. |

---

## The Two Scenarios

Every framework is measured against two enterprise workflow patterns:

**GEW — Generic Enterprise Workflow**
A 5-step approval chain representative of document processing, compliance, and back-office automation:
```
data_retrieval → risk_assessment → human_approval_gate → action_execution → audit_log
```
Mock infrastructure: external data API (port 8001), idempotent CRM write with idempotency key (port 8002), human-in-the-loop approval polling (port 8003).

**TCW — Telco CVM/NBA Workflow**
A 5-step customer value management pipeline representative of personalisation, recommendation, and real-time decisioning:
```
customer_graph_query → propensity_scoring → eligibility_check → offer_personalisation → channel_dispatch
```
Mock infrastructure: Neo4j customer 360 stub (port 8101), ML propensity + eligibility endpoint (port 8102), multi-channel dispatch with receipt audit (port 8103).

Both scenarios run in `DRY_RUN=true` mode for full reproducibility — no LLM calls, no external services required.

---

## Score Matrix

| Framework | P1 Durable | P2 Blast-Radius | P3 Observability | P4 Packaging | P5 Migration | **POI** |
|---|---|---|---|---|---|---|
| LangGraph | 2 | **3** | 1 | 2 | 1 | **9** |
| AutoGen/MS | 0 | 1 | 1 | 2 | 1 | 5 |
| OpenAI SDK | 0 | 1 | 1 | 2 | **3** | 7 |
| Google ADK | 2 | 1 | 1 | 2 | 2 | 8 |
| Bedrock/Strands | 0 | 1 | **2** | **3** | **3** | **9** |

Scores are 0–3 per pillar; maximum POI is 15. See Article 1 for the full scoring rubric.

---

## Operability Tax (OT-LOC)

Lines of custom scaffolding your team must write and maintain to reach production-grade operability:

| Framework | OT-LOC | POI |
|---|---|---|
| OpenAI SDK | 124 | 7 |
| AutoGen/MS | 135 | 5 |
| LangGraph | 179 | 9 |
| Bedrock/Strands | 195 | 9 |
| Google ADK | 221 | 8 |

OT-LOC is the sum of P1 checkpoint wrapper, P2 kill-switch glue, P3 OTel exporter shim, and P4 Helm template lines. All values are counted by code or documented as named lists in source — no self-reported estimates.

---

## Per-Framework Findings

### LangGraph — POI 9, OT 179 LOC

**The headline finding: the only framework with active runtime blast-radius containment.**

LangGraph's graph executor enforces a `recursion_limit` by default. When an agent loop exceeds it, the framework raises a `GraphRecursionError` — a structured, catchable Python exception that application code can handle, log, and escalate. Every other framework tested relies on a platform-level SIGTERM as the only containment mechanism.

This single difference accounts for P2=3 (vs P2=1 for all others) and is the primary driver of LangGraph's POI lead.

**P1=2 (not 3) — the checkpoint portability gap:**
LangGraph's `MemorySaver` checkpoints mid-run with a parseable format and resume works. But MemorySaver is in-process only. Cross-process portability requires `PostgresSaver` — one configuration change, no code change, but still an operator step. Score-3 requires the portable backend to be the default. The gap costs 0 score points on P1 but adds to OT-LOC (the PostgresSaver wiring and psycopg Dockerfile layer are the largest single contributor to LangGraph's 179 LOC tax).

**P5=1 — checkpoint schema migrations:**
LangGraph's checkpoint format changes across minor versions. The upgrade guide documents migration steps, but co-ordinated deploys across services are still required. This is the operability cost of a framework that is evolving quickly.

**The OT paradox:** LangGraph has the highest POI but not the lowest OT. Its 179 LOC of scaffolding is the price of its P1 capability. A team that needs durable, resumable workflows pays that cost; a team that doesn't can choose a framework with lower OT.

---

### Microsoft AutoGen (AgentChat) — POI 5, OT 135 LOC

**The headline finding: strongest multi-agent coordination patterns, weakest production operability.**

AutoGen's GroupChat (`RoundRobinGroupChat`, `SelectorGroupChat`) is the most expressive multi-agent coordination primitive of the five frameworks. For workflows requiring dynamic role assignment, consensus-based decisions, or multi-specialist orchestration, it offers patterns the other frameworks don't provide natively.

**P1=0 — no native checkpointing:**
GroupChat conversation state is in-memory only. A crash at any step means a full restart. There is no built-in mechanism to resume from a checkpoint. Reaching score-3 requires a custom state-serialisation wrapper that snapshots the conversation history to a durable store.

**P5=1 — highest breaking-change frequency:**
AutoGen averaged 3.1 breaking changes per release across the versions examined. The v0.2 → v0.4 transition alone renamed core APIs and changed agent configuration schemas. For a team running AutoGen across 20 services, a quarterly framework upgrade is a non-trivial coordination event.

**The honest assessment:** AutoGen is well-suited to research environments and rapid prototyping where multi-agent coordination patterns matter more than crash recovery and upgrade stability. For enterprise production deployments requiring durable execution and predictable upgrade costs, every other framework in this benchmark scores higher.

---

### OpenAI Agents SDK — POI 7, OT 124 LOC

**The headline finding: lowest operational overhead to run, least control over what you're running.**

The OpenAI Agents SDK has the most stable changelog of the five frameworks — 0.5 breaking changes per release on average, no checkpoint schema migrations, no prompt rewrites required across the versions examined. Quarterly upgrades are the lightest of any framework tested.

**P1=0 — vendor-managed checkpoint state:**
Agent state is managed on OpenAI's backend, not on your infrastructure. Resume works — but only if you trust OpenAI's persistence layer and accept that the checkpoint is not inspectable, not portable, and not under your control. If OpenAI's backend has an outage, your agents cannot resume. If you migrate away from OpenAI, your checkpoint state does not migrate with you.

**The OT paradox (inverted):** lowest OT (124 LOC) with POI=7. The low scaffolding cost comes from not needing to write checkpoint code — because the framework delegates that to a vendor backend. This is a trade-off, not a win. You are paying for convenience with vendor lock-in rather than with lines of code.

**Best suited for:** teams running stateless or short-horizon agents where checkpoint recovery is not a requirement, and where API stability and low upgrade overhead are the primary concerns.

---

### Google ADK — POI 8, OT 221 LOC

**The headline finding: solid durability story, highest packaging overhead due to GCP assumptions.**

Google ADK's `InMemorySessionService` provides native checkpointing with a parseable JSON format and working resume out of the box — matching LangGraph on P1. The session backend is swappable (to Cloud Firestore, Vertex AI) — but only to GCP services.

**P4=2 — the cloud coupling cost:**
Deploying ADK to a standard Kubernetes cluster requires three mandatory environment variables that are not standard K8s primitives: `ADK_RUNNER=local` (to disable the Cloud Run default runner), `GOOGLE_CLOUD_PROJECT` (required even for non-GCP deployments), and `LITELLM_BASE_URL` (to override ADK's default AI Platform routing). Each requires a framework-specific Helm template annotation and a Kyverno policy exception. This is the largest source of packaging overhead across the five frameworks and the primary driver of ADK's 221 LOC OT — the highest of the five.

**Best suited for:** teams already on GCP infrastructure, where the session backend swap to Firestore is straightforward and the cloud coupling assumptions are already met by the target environment.

---

### Amazon Bedrock / Strands Agents — POI 9, OT 195 LOC

**The headline finding: ties LangGraph at POI=9 via a completely different operability profile.**

Where LangGraph wins on durability and containment (P1, P2), Strands wins on packaging and API stability (P4, P5). The two frameworks reach the same total POI score through entirely different strengths.

**P4=3 — zero framework-specific K8s workarounds:**
Strands is the only framework with zero framework-specific Kubernetes workarounds. OTel is configured via the standard `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable; secrets are standard env vars. The Helm chart passes all Kyverno ClusterPolicies without exceptions or hacks. For platform teams running a shared golden-path Helm chart across many agent services, Strands is the easiest to standardise.

**P5=3 — most stable API:**
0.4 breaking changes per release on average. No checkpoint schema migrations. No prompt rewrites required. The most predictable upgrade path of the five frameworks.

**P3=2 (not 3):**
Strands emits all four required Gen-AI OTel attributes natively — but still requires `strands-otel` to be wired as a custom exporter. The attributes are present; the plumbing is not automatic. This is a half-step from score-3 that a future SDK update could close.

**P1=0 — the critical gap:**
No native checkpoint/resume. A crash at step 4 means full restart from step 1. Reaching score-3 P1 requires a custom state-serialisation wrapper (~80 LOC) — the primary driver of Strands' 195 LOC OT.

**Best suited for:** teams prioritising packaging simplicity, upgrade stability, and AWS ecosystem alignment, where workflow durations are short enough that crash-and-restart from step 1 is acceptable.

---

## Ranking and Stability

### Equal-Weight Ranking

Tiebreak: OT-LOC ascending (less maintenance burden wins).

| Rank | Framework | POI | OT-LOC | Primary strength |
|---|---|---|---|---|
| #1 | LangGraph | 9 | 179 | Blast-radius containment (P2=3, unique) |
| #2 | Bedrock/Strands | 9 | 195 | Packaging + API stability (P4=3, P5=3) |
| #3 | Google ADK | 8 | 221 | Durability (P1=2) with GCP coupling cost |
| #4 | OpenAI SDK | 7 | 124 | Lowest OT, vendor-managed state |
| #5 | AutoGen/MS | 5 | 135 | Multi-agent patterns, weakest operability |

### Rank Stability Under Different Pillar Weights

Equal weights are an assumption. The benchmark re-ran the ranking under 1,000 random weight vectors (Dirichlet uniform distribution) to test how sensitive the conclusions are to that assumption.

| Pairwise comparison | % of weight vectors where order holds | Verdict |
|---|---|---|
| LangGraph > Bedrock/Strands | 48% | **Fragile** — effectively a coin flip. The POI=9 tie reflects genuine closeness. |
| Bedrock/Strands > Google ADK | 71% | Contested — Strands' P4/P5 offset by ADK's P1 lead under high durability weighting. |
| Google ADK > OpenAI SDK | 67% | Contested — flips when P5 (stability) is weighted more heavily than P1 (durability). |
| OpenAI SDK > AutoGen | 100% | **Stable** — OpenAI SDK categorically ahead regardless of weights. |

**Full ranking unchanged: 15% of draws.**

The confident claims:
- AutoGen trails the field under any reasonable weighting.
- LangGraph and Strands are genuinely close — the tiebreak is OT-LOC, not a clear capability difference.
- The mid-tier rankings (#3 and #4) are sensitive to whether your team weights durability or stability more heavily.

---

## Conclusions

**If your team needs durable, resumable workflows and cannot tolerate unbounded loops:** LangGraph. It is the only framework with active runtime blast-radius containment, and its checkpoint story is the strongest for long-horizon workflows. The OT cost is real but justified.

**If your team prioritises packaging simplicity, upgrade predictability, and AWS alignment:** Bedrock/Strands. The P4=3 packaging score means standardised Helm charts without framework-specific exceptions; the P5=3 stability score means the lightest upgrade burden. The missing P1 is the trade-off.

**If your team is already on GCP:** Google ADK. The cloud coupling assumptions are already met, the P1 story is solid, and the packaging overhead disappears in a GCP-native environment.

**If upgrade stability and low scaffolding overhead are the primary constraints:** OpenAI SDK. Lowest OT, most stable changelog. Accept vendor-managed state as a constraint.

**If you need multi-agent coordination patterns above all else and can tolerate the operability gaps:** AutoGen. But go in knowing you are building P1 checkpointing from scratch and budgeting for 3+ breaking changes per release cycle.

---

## How to Reproduce

The full benchmark — harness, adapters for all five frameworks, Helm charts, Kyverno policies, scenario implementations, and analysis scripts — is at:

**[github.com/ketan1602/platform-operability-index](https://github.com/ketan1602/platform-operability-index)**

```bash
git clone https://github.com/ketan1602/platform-operability-index
cd platform-operability-index
pip install pydantic pyyaml structlog requests

# Reproduce the full score matrix (no credentials required)
DRY_RUN=true python3 -m harness.run_all

# Generate score matrix, OT table, ranking, sensitivity analysis
python3 analysis/poi_report.py
```

The output matches the score matrix and ranking in this article exactly. Every scoring function is a pure Python function in `harness/shared/scoring.py` — readable, testable, forkable.

To add a new framework: create an adapter directory, implement `_run_p1` through `_run_p5`, add scenario implementations for GEW and TCW, and add the framework to `harness/run_all.py`. The harness discovers it automatically.
