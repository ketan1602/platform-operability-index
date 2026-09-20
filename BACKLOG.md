# POI Benchmark — Improvement Backlog

Items to implement when resuming. Ordered by tier (impact/effort).
Do not re-litigate decisions already made — treat this as a pick-up list.

---

## Reference: Three metric types (governs when statistics apply)

| Type | Definition | Statistical need |
|---|---|---|
| **Deterministic property** | Same answer every run — it either exists or it doesn't | N=1 is correct. Adding runs adds noise, not signal. |
| **Empirical measurement** | Timing, counts — varies with system state across runs | N≥10 runs; bootstrap CI for timing; Wilson/binomial CI for counts |
| **Researcher judgment / desk research** | Changelog reading, time estimates, hack lists | Inter-rater reliability (Cohen's κ or Krippendorff's α) + documented protocol |

Most of POI's credibility problem comes from treating type 2 and type 3 metrics with type 1 certainty (single observation reported as fact).

---

## Tier 1 — Before any external publication (low effort, high impact)

These require no new runs. Can be done against existing code and data.

### T1-1 — P4: Remove self-reported time fields from scoring

**What:** Remove `template_creation_time_hrs` and `deployment_time_hrs` from `score_p4()`.
These are the only self-reported, unreproducible values currently feeding a score.

**Where:** `harness/shared/scoring.py` → `score_p4()`, `harness/shared/pillar_models.py`

**What to do:**
- Remove both fields from `score_p4()` decision logic
- Keep fields in `P4Measurements` as metadata annotations (not scored)
- Update all five `p4_measure.py` files accordingly

---

### T1-2 — P4: Add catalog/registry label check (new field)

**What:** Add `catalog_labels_present: bool` to `P4Measurements`.
Tests whether the Helm chart produces pods with the full standard K8s ownership label set.
Technology-agnostic — works with Backstage, OpsLevel, Port, Cortex, or any catalog tool.

**Required labels (all five must be present):**
```
app.kubernetes.io/name
app.kubernetes.io/component
app.kubernetes.io/version
app.kubernetes.io/part-of
app.kubernetes.io/managed-by
```

**Where:**
- `harness/shared/pillar_models.py` — add `catalog_labels_present: Optional[bool] = None`
- `harness/shared/scoring.py` → `score_p4()` — factor into score (presence of all five → score 3 eligible)
- Each `harness/adapters/<fw>/p4_measure.py` — check rendered chart YAML for labels
- Each `charts/poi-<fw>/templates/*.yaml` — add missing labels where absent

**Measurement:** Deterministic. Parse all `templates/*.yaml` in each Helm chart. Check for all five `app.kubernetes.io/*` labels. N=1 sufficient.

---

### T1-3 — P4: Second rater for framework_specific_hacks_required

**What:** The `framework_specific_hacks_required` field is a subjective list produced by one reviewer. Two independent reviewers listing hacks for each framework, measured by weighted Cohen's κ, converts it from an opinion into a measurement.

**Protocol:**
1. Second reviewer independently reads each framework's Helm chart and p4_measure.py hacks list
2. Lists hacks without seeing the first reviewer's list
3. Compute weighted Cohen's κ on overlap. Target κ ≥ 0.6 before publishing.
4. If κ < 0.6 resolve disagreements, re-rate

**Statistical method:** Weighted Cohen's κ (agentlens `stats/_kappa.py` — copy)

**Where:** Document κ value in each `harness/adapters/<fw>/p4_measure.py` docstring alongside the hacks list.

**Effort:** One afternoon — no code changes, just a second human review pass.

---

### T1-4 — P5: Formal protocol and second rater

**What:** Replace the current single-researcher changelog assessments with a documented, reproducible protocol.

**Protocol:**

1. **Define "breaking change"** (document this definition in each `p5_measure.py` docstring):
   > Public API removal, signature change, or behaviour change not gated by a deprecation warning. Excludes internal modules, private underscore names, and anything labelled experimental.

2. **Sample window:** Last 12 minor releases of each framework, or all releases in the past 12 months — whichever is smaller. Document the exact version range in `p5_measure.py`.

3. **Two independent raters** classify each release note item as: `breaking` / `non-breaking` / `ambiguous`. Resolve ambiguous after first pass.

4. **Compute Cohen's κ** (weighted, ordinal). If κ < 0.6, resolve disagreements and re-rate. Target κ ≥ 0.7 before publishing.

5. **Report:** mean ± 95% CI across the sampled releases (bootstrap, since N is typically 8–12 releases).

**Where:** Each `harness/adapters/<fw>/p5_measure.py` — add version range, source links, and rater agreement κ to docstring.

**Replace `estimated_fleet_upgrade_hrs_per_release_cycle`:**
- Remove the invented "10 agents × N hrs" formula
- Replace with: actual time to upgrade the POI test harness itself from framework version N to N+1
- This is observable, reproducible, and directly relevant
- Report as n=1 anecdotal observation with explicit label — honest, not inflated

---

### T1-5 — Composite: Weight sensitivity analysis (Dirichlet)

**What:** Re-run ranking under 10,000 random weight vectors drawn from Dirichlet(1,1,1,1,1) (uniform over the weight simplex). Report: does the ranking hold under > 80% of weight draws?

**Where:** `analysis/poi_report.py` — add `_sensitivity_analysis(matrix)` function (~20 lines)

**Output:**
```
=== Weight Sensitivity (10,000 Dirichlet draws) ===
LangGraph   ranks #1 in 71%  of draws
Strands     ranks #1 in 29%  of draws
Google ADK  ranks #3 in 84%  of draws
...
```

This converts an equal-weight assumption into an auditable claim: "the ranking is robust to reasonable weight variation."

---

### T1-6 — Composite: Spearman rank correlation (fixed vs idiomatic)

**What:** Compute Spearman's ρ between fixed-implementation POI scores and idiomatic-implementation POI scores across the 5 frameworks. If ρ > 0.8, the fixed/idiomatic distinction doesn't change conclusions.

**Where:** `analysis/poi_report.py` — add `_rank_stability(records)` function (~10 lines)

**Cost:** 5 lines of scipy. Already have both run types in results/.

---

## Tier 2 — During real LLM runs (medium effort, high validity)

Requires live framework installations and real inference. Do after real LLM credentials are available.

### T2-1 — P1: N=20 timed runs with bootstrap CI

**What:** Run T2 (crash/resume) and T3 (idempotency) 20 times per framework. Report bootstrap 95% CI on `resume_latency_ms` instead of a single point measurement.

**Output format change:** Replace `resume_latency_ms: int` in YAML with:
```yaml
resume_latency_ms:
  mean: 312
  ci_low: 287
  ci_high: 341
  n: 20
  method: cluster_bootstrap_studentised
```

**Statistical method:** Studentised cluster bootstrap, 10,000 resamples (from agentlens `stats/bootstrap.py` — copy implementation into `harness/shared/stats/bootstrap.py`).

**Where:** `harness/adapters/langgraph/p1_measure.py` → `_t2_resume()` (run N times, aggregate)

---

### T2-2 — P1/P2: Wilson CI on binary outcomes + exact binomial for boolean properties

**What:** Two related additions:

**Wilson score CI** — for count metrics (`duplicate_tool_calls_on_mid_write`, `credential_bleed_events`, `steps_re_executed_on_resume`):
- When count=0 over N=20 runs: 95% CI upper bound ≈ 0.14 for N=20
- Turns "it never happened" into "it happened at most 14% of the time at 95% confidence" — defensible

**Exact binomial CI** — for boolean properties measured over N runs (`runaway_loop_contained_by_default`):
- Always contained across 20 runs → report: 20/20 = 1.0 [0.83, 1.0] 95% CI
- Use exact binomial (not normal approximation) below N=30

**McNemar's test** — for pairwise framework comparison on binary outcomes:
- "Did framework A have duplicate tool calls where framework B did not?" — McNemar answers this
- Separate from Wilson CI (per-framework proportion) and from Wilcoxon (continuous timing)
- From agentlens `stats/_mcnemar.py` — exact form below 25 discordant pairs

**Where:**
- Add `harness/shared/stats/wilson.py` (~10 lines) for Wilson CI and exact binomial
- Add McNemar via agentlens copy into `harness/shared/stats/mcnemar.py`
- Use in all P1/P2 adapters after N=20 runs

---

### T2-3 — P2 F2–F5: Live FI-3 failure injection tests

**What:** Currently only LangGraph (F1) has a live FI-3 runaway loop test. F2–F5 have hardcoded assertions based on framework documentation. To be credible, all five must run the test.

**What to do:** Install each framework in its per-adapter venv. Run `_fi3_runaway_test()` equivalent for AutoGen, OpenAI SDK, Google ADK, Strands. Measure:
- `runaway_loop_contained_by_default` — does the framework halt the loop natively?
- `halt_latency_ms` — how fast?
- `credential_bleed_events` — run FI-4 injection, count leaks

**Estimated effort:** One afternoon per framework (4 frameworks × ~3 hrs = 12 hrs total).

---

### T2-4 — P3: One live run per framework with Prometheus

**What:** Run each framework once with `PROMETHEUS_URL` configured and `OTEL_EXPORTER_OTLP_ENDPOINT` set. Record the actual emitted OTel attributes. Replace all `_KNOWN_MISSING` desk-research fallback values with observed data.

**What to set up:** Prometheus + OTLP collector (docker-compose). Start each framework's workflow, let it run one real task, scrape spans.

**Output:** Replace `_KNOWN_MISSING = ["gen_ai.usage.input_tokens", ...]` with observed list in each `p3_measure.py`.

**This is the single most impactful observability fix** — converts desk research into measurement for P3 across all 5 frameworks.

---

### T2-5 — Pairwise framework comparison: Wilcoxon + Cliff's delta

**What:** After N=20 runs exist, compute pairwise Wilcoxon signed-rank tests for all timing measurements across framework pairs. Report Cliff's delta as effect size.

**Multiple comparison correction:** Benjamini-Hochberg FDR at q=0.05 across all C(5,2)×2=20 pairwise timing tests.

**From agentlens** (copy into `harness/shared/stats/`):
- `_wilcoxon.py` → Wilcoxon + Cliff's delta
- `multiplicity.py` → BH-FDR

**Cliff's delta thresholds:**
- < 0.147 negligible
- < 0.330 small
- < 0.474 medium
- ≥ 0.474 large

Only report framework comparisons as "significant" where Cliff's δ ≥ 0.33 (small effect minimum) AND q < 0.05 after BH correction.

---

### T2-6 — Composite: Parametric bootstrap CI on POI score

**What:** Propagate measurement uncertainty through the scoring function to produce a CI on each framework's composite POI score. Enables claims like: "LangGraph: POI 9 [7, 10] 95% CI". Requires N runs per metric to exist (do after T2-1).

**Method:** For each of 10,000 bootstrap resamples:
1. Sample N timing/count measurements for each metric with replacement
2. Compute P1–P5 scores from the resampled measurements
3. Sum to POI composite
4. Report 2.5th and 97.5th percentiles as CI bounds

**Where:** `analysis/poi_report.py` — add `_composite_ci(records, n_resamples=10_000)` function (~30 lines)

**Depends on:** T2-1 (N=20 runs must exist before this is meaningful)

---

## Tier 3 — For Article 7 (agents-at-scale multi-framework benchmark)

Full statistical treatment. Do after Articles 1–6 of agents-at-scale are complete.

### T3-1 — Internal consistency: Cronbach's α on composite

**What:** Test whether the 5 pillars form a coherent composite (all measuring "operability"). Cronbach's α = (k/(k-1)) × (1 - Σσᵢ²/σₜ²). Target α > 0.65. If α < 0.50, report pillars separately — the sum is not meaningful.

**~20 lines to implement.** Not in agentlens — add to `harness/shared/stats/cronbach.py`.

---

### T3-2 — Scale dimension: Load curves per pillar

**What:** Add a scale sub-test to each pillar. Run at concurrency C ∈ {1, 5, 10, 25, 50} agents simultaneously. Produce a load curve for each pillar metric.

**Key measurements:**
- P1-S: `resume_p99_latency_ms` vs C — where does checkpoint backend saturate?
- P2-S: `concurrent_runaway_isolation` — 10 simultaneous FI-3; are all isolated independently?
- P3-S: `span_drop_rate_pct_at_100_spans_per_sec` — does OTel exporter backpressure correctly?
- P4-S: `horizontal_scale_compatible` (stateless pods?), `hpa_configurable`
- P5-S: `rolling_upgrade_simultaneous_versions`, `checkpoint_forward_compat`

**Statistical treatment:**
- Bootstrap CI at each C value (10 trial runs per C level)
- Fit linear/polynomial model to the load curve; report R² and inflection point (concurrency level where p99 latency doubles from C=1 baseline)
- Amdahl's Law framing: serialized fraction s = 1 - speedup/C; report s per framework

**Key publishable finding:** A framework whose checkpoint write is a mutex (e.g. LangGraph MemorySaver) hits a scaling ceiling at ~8–10 concurrent agents regardless of pod count — Amdahl's Law applied to the checkpoint serialization fraction. This is a concrete, quantified operability limit that no single-agent test can reveal.

**This becomes the primary Article 7 contribution** — what the agents-at-scale build reveals about each framework's operability under real fleet load.

---

### T3-3 — GLMM with scenario as random effect

**What:** Separate framework signal from scenario noise using a mixed effects model. Framework as fixed effect, scenario (GEW/TCW) as random effect. Allows claim: "LangGraph's P1 score advantage holds regardless of scenario."

**From agentlens** (copy `glmm.py`, `_reml.py`, `_gls.py`). Already implemented and citable.

---

### T3-4 — Kruskal-Wallis + Dunn post-hoc (5-framework pillar comparison)

**What:** Non-parametric equivalent of one-way ANOVA for comparing all 5 frameworks on each ordinal pillar score. Dunn post-hoc with Holm correction for pairwise follow-up.

**~40 lines.** Add to `harness/shared/stats/nonparametric.py`.

---

### T3-5 — External replication

**What:** One engineer not involved in the benchmark reproduces P1–P3 scores independently using only the repo and `.env.example`. Document differences if any.

**Minimum bar for conference submission.** Schedule after Tier 2 is complete.

---

## Statistical methods source

| Method | Source | Notes |
|---|---|---|
| Cluster bootstrap CI | agentlens `stats/bootstrap.py` — copy, do not import | Cites Efron 1979; Davison & Hinkley 1997 |
| Wilcoxon + Cliff's delta | agentlens `stats/_wilcoxon.py` — copy | Cites Demšar 2006 JMLR; Cliff 1993 |
| McNemar's test | agentlens `stats/_mcnemar.py` — copy | Cites Dietterich 1998; for paired binary comparisons across frameworks |
| BH-FDR | agentlens `stats/multiplicity.py` — copy | Cites Benjamini & Hochberg 1995 |
| Cohen's κ (weighted) | agentlens `stats/_kappa.py` — copy | Cites Cohen 1960; threshold 0.6 from agentlens |
| Krippendorff's α | agentlens `stats/_alpha.py` — copy | Cites Krippendorff 1970 |
| GLMM / REML | agentlens `stats/glmm.py` — copy | Cites Demšar 2006 |
| Wilson score CI | Implement fresh (~10 lines) | Standard; scipy-free |
| Cronbach's α | Implement fresh (~20 lines) | Not in agentlens |
| Dirichlet sensitivity | Implement fresh (~15 lines) | Not in agentlens |
| Spearman's ρ | scipy.stats.spearmanr (5 lines) | Standard |
| Kruskal-Wallis + Dunn | Implement fresh (~40 lines) | Not in agentlens |

Copy agentlens implementations into `harness/shared/stats/` — do not create a runtime dependency on the agentlens package. Attribution stays in the docstrings.

---

## Sizing table

| Purpose | Runs per framework | Statistical claims possible |
|---|---|---|
| Current (DRY_RUN) | 1 | Functional coverage only — no statistical claims |
| Internal decision aid | 10 | Bootstrap CI on timing; Wilson CI on binary outcomes |
| External blog / article | 20 | Wilcoxon + Cliff's delta at 80% power for medium effects (δ ≥ 0.33) |
| Conference paper | ≥ 30 | GLMM; full BH-FDR; Cronbach's α |
| Article 7 publication | ≥ 50 + load curves | Scale dimension; external replication |

---

## Context

- **POI benchmark repo:** `platform-operability-index` (private GitHub: ketan1602/platform-operability-index)
- **Article 7 scope:** POI benchmark + scale dimension, positioned as the framework-selection layer for the agents-at-scale series (Articles 1–6 use LangGraph only)
- **AgentLens relationship:** Not integrated into POI measurements (orthogonal concerns). Statistical library can be copied into `harness/shared/stats/` with attribution.
- **Real LLM runs:** User will perform. Required before Tier 2 items.
- **Scale tests (T3-2):** Designed to use the agents-at-scale simulator concurrency levels (1/5/10/25/50/100) as the test harness — natural statistical treatment via repeated runs at each C.
