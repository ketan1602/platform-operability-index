// Results rendering: score matrix, OT-LOC bars, ranking, sensitivity.
const PILLARS = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"];
const PILLAR_LABELS = {
  p1: "P1 Durable execution", p2: "P2 Blast radius", p3: "P3 Observability",
  p4: "P4 Packageability", p5: "P5 Migration fragility",
  p6: "P6 Portability", p7: "P7 Developer experience", p8: "P8 Security posture",
};
const TAG_STATUS = { stable: "success", contested: "warning", fragile: "error" };
const TAG_ICON = { stable: "●", contested: "▲", fragile: "■" };

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") node.textContent = v;
    else if (k === "tip") node.dataset.tip = v;
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) node.append(c);
  return node;
}

function bindTooltips(root) {
  const tip = document.getElementById("tooltip");
  root.querySelectorAll("[data-tip]").forEach((n) => {
    n.addEventListener("mouseenter", () => { tip.textContent = n.dataset.tip; tip.hidden = false; });
    n.addEventListener("mousemove", (e) => {
      tip.style.left = `${e.clientX + 12}px`; tip.style.top = `${e.clientY + 12}px`;
    });
    n.addEventListener("mouseleave", () => { tip.hidden = true; });
  });
}

function renderMatrix(r) {
  const head = el("tr", {}, [el("th", { text: "Framework" }),
    ...PILLARS.map((p) => el("th", { text: p.toUpperCase(), title: PILLAR_LABELS[p] })),
    el("th", { text: "POI" })]);
  const rows = r.ranking.map((fid) => {
    const s = r.matrix[fid];
    const cells = PILLARS.map((p) => el("td", {
      class: `heat heat-${s[p] ?? "na"}`, text: s[p] ?? "–",
      tip: `${r.names[fid]} · ${PILLAR_LABELS[p]}: ${s[p] ?? "not measured"} / 3`,
    }));
    return el("tr", {}, [el("th", { scope: "row", text: r.names[fid] }), ...cells,
      el("td", { class: "total", text: s.poi_total })]);
  });
  return el("table", { class: "matrix" }, [el("thead", {}, head), el("tbody", {}, rows)]);
}

function renderOT(r) {
  const max = Math.max(...Object.values(r.ot), 1);
  const order = Object.keys(r.ot).sort((a, b) => r.ot[a] - r.ot[b]);
  return el("div", { class: "bars" }, order.map((fid) => el("div", { class: "bar-row" }, [
    el("span", { class: "bar-label", text: r.names[fid] }),
    el("div", { class: "bar-track" }, el("div", {
      class: "bar-fill", style: `width:${(r.ot[fid] / max) * 100}%`,
      tip: `${r.names[fid]}: ${r.ot[fid]} LOC of custom scaffolding`,
    })),
    el("span", { class: "bar-value", text: `${r.ot[fid]}` }),
  ])));
}

function renderRanking(r) {
  return r.ranking.map((fid) => el("li", {}, [
    el("strong", { text: r.names[fid] }),
    el("span", { class: "muted", text: ` POI ${r.matrix[fid].poi_total} · OT ${r.ot[fid] ?? "–"} LOC` }),
  ]));
}

function evidenceText(cell) {
  if (cell.median === null) return `inconclusive ×${cell.inconclusive}`;
  const range = cell.min === cell.max ? "" : ` [${cell.min}–${cell.max}]`;
  const inc = cell.inconclusive ? ` · ${cell.inconclusive} inc.` : "";
  return `${cell.median}${range} · n${cell.n}${inc}`;
}

function renderEvidence(r) {
  const evidencePillars = ["p1", "p2", "p3", "p6", "p7", "p8"];
  const head = el("tr", {}, [el("th", { text: "Framework" }),
    ...evidencePillars.map((p) => el("th", { text: PILLAR_LABELS[p] }))]);
  const rows = r.ranking.map((fid) => el("tr", {}, [
    el("th", { scope: "row", text: `${r.names[fid]}${r.source[fid] === "baseline" ? " (baseline)" : ""}` }),
    ...evidencePillars.map((p) => el("td", { class: "evidence" },
      Object.entries(r.evidence[fid][p] || {}).map(([sc, cell]) =>
        el("div", { text: `${sc}: ${evidenceText(cell)}` })))),
  ]));
  return el("table", { class: "matrix evidence-table" }, [el("thead", {}, head), el("tbody", {}, rows)]);
}

function renderSensitivity(r) {
  const s = r.sensitivity;
  const rows = s.pairs.map((p) => el("div", { class: "bar-row" }, [
    el("span", { class: "bar-label wide", text: `${r.names[p.a]} > ${r.names[p.b]}` }),
    el("div", { class: "bar-track" }, el("div", {
      class: "bar-fill", style: `width:${p.pct}%`,
      tip: `Order holds in ${p.pct}% of ${s.samples} random weightings`,
    })),
    el("span", { class: "bar-value", text: `${p.pct}%` }),
    el("span", { class: `status status-${TAG_STATUS[p.tag]}`, text: `${TAG_ICON[p.tag]} ${p.tag}` }),
  ]));
  rows.push(el("p", { class: "muted", text: `Full ranking unchanged in ${s.full_rank_hold_pct}% of draws.` }));
  return el("div", { class: "bars" }, rows);
}

function renderFinOps(r) {
  const vals = Object.fromEntries(r.ranking.map((fid) => [fid, r.finops[fid]?.total_input_tokens ?? 0]));
  const max = Math.max(...Object.values(vals), 1);
  const order = [...r.ranking].sort((a, b) => vals[a] - vals[b]);
  const rows = order.map((fid) => el("div", { class: "bar-row" }, [
    el("span", { class: "bar-label", text: r.names[fid] }),
    el("div", { class: "bar-track" }, el("div", {
      class: "bar-fill", style: `width:${(vals[fid] / max) * 100}%`,
      tip: `${r.names[fid]}: ${vals[fid].toLocaleString()} input tokens · est $${r.finops[fid]?.estimated_run_cost_usd ?? "–"}`,
    })),
    el("span", { class: "bar-value", text: vals[fid] > 0 ? `${(vals[fid] / 1000).toFixed(0)}k` : "–" }),
  ]));
  return el("div", { class: "bars" }, rows);
}

function renderPerf(r) {
  const vals = Object.fromEntries(r.ranking.map((fid) => [fid, r.perf[fid]?.inter_tool_latency_ms ?? null]));
  const avail = Object.values(vals).filter((v) => v !== null);
  const max = Math.max(...avail, 1);
  const order = [...r.ranking].sort((a, b) => (vals[a] ?? Infinity) - (vals[b] ?? Infinity));
  const rows = order.map((fid) => {
    const v = vals[fid];
    const mem = r.perf[fid]?.peak_memory_rss_mb;
    return el("div", { class: "bar-row" }, [
      el("span", { class: "bar-label", text: r.names[fid] }),
      el("div", { class: "bar-track" }, el("div", {
        class: "bar-fill", style: `width:${v !== null ? (v / max) * 100 : 0}%`,
        tip: `${r.names[fid]}: ${v ?? "–"} ms inter-tool · ${mem ?? "–"} MB peak RSS`,
      })),
      el("span", { class: "bar-value", text: v !== null ? `${v}ms` : "–" }),
    ]);
  });
  return el("div", { class: "bars" }, rows);
}

async function loadResults() {
  const mode = document.querySelector("input[name=results-mode]:checked").value;
  const res = await fetch(`/api/v1/results?mode=${mode}`);
  const r = await res.json();
  const ids = ["matrix", "ot", "ranking", "evidence", "sensitivity"];
  ids.forEach((id) => document.getElementById(id).replaceChildren());
  const meta = document.getElementById("results-meta");
  if (!r.run_count) {
    meta.textContent = `No ${mode === "live" ? "live" : "dry-run"} results yet — start a run.`;
    document.getElementById("sens-meta").textContent = "";
    return;
  }
  meta.textContent = `${r.run_count} run result files aggregated` +
    (r.errors ? ` · ${r.errors} failed runs excluded.` : ".");
  document.getElementById("matrix").append(renderMatrix(r));
  document.getElementById("ot").append(renderOT(r));
  document.getElementById("ranking").append(...renderRanking(r));
  document.getElementById("evidence").append(renderEvidence(r));
  if (r.finops) document.getElementById("finops").append(renderFinOps(r));
  if (r.perf) document.getElementById("perf").append(renderPerf(r));
  document.getElementById("sensitivity").append(renderSensitivity(r));
  document.getElementById("sens-meta").textContent = `(${r.sensitivity.samples} Dirichlet weight samples)`;
  bindTooltips(document.getElementById("results-card"));
}

document.querySelectorAll("input[name=results-mode]").forEach((i) => i.addEventListener("change", loadResults));
