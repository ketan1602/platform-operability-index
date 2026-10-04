// Results rendering: score matrix, OT-LOC bars, ranking, sensitivity.
const PILLARS = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"];
const PILLAR_LABELS = {
  p1: "P1 Durable execution", p2: "P2 Blast radius", p3: "P3 Observability",
  p4: "P4 Packageability", p5: "P5 Migration fragility",
  p6: "P6 Portability", p7: "P7 Developer experience", p8: "P8 Security posture",
  p9: "P9 Ops experience",
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
    const cells = PILLARS.map((p) => {
      const raw = s[p];
      const display = raw == null ? "–" : Number.isInteger(raw) ? raw : raw.toFixed(1);
      const heatKey = raw == null ? "na" : Math.min(Math.floor(raw + 0.5), 3);
      return el("td", {
        class: `heat heat-${heatKey}`, text: display,
        tip: `${r.names[fid]} · ${PILLAR_LABELS[p]}: ${display} / 3`,
      });
    });
    const total = s.poi_total;
    const totalDisplay = total == null ? "–" : Number.isInteger(total) ? total : total.toFixed(1);
    return el("tr", {}, [el("th", { scope: "row", text: r.names[fid] }), ...cells,
      el("td", { class: "total", text: totalDisplay })]);
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

function fmtScore(v) {
  if (v == null) return "–";
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

function renderRanking(r) {
  return r.ranking.map((fid) => el("li", {}, [
    el("strong", { text: r.names[fid] }),
    el("span", { class: "muted", text: ` POI ${fmtScore(r.matrix[fid].poi_total)} · OT ${r.ot[fid] ?? "–"} LOC` }),
  ]));
}

function evidenceText(cell) {
  if (cell.median === null) return `inconclusive ×${cell.inconclusive}`;
  const range = cell.min === cell.max ? "" : ` [${fmtScore(cell.min)}–${fmtScore(cell.max)}]`;
  const inc = cell.inconclusive ? ` · ${cell.inconclusive} inc.` : "";
  return `${fmtScore(cell.median)}${range} · n${cell.n}${inc}`;
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
  const vals = Object.fromEntries(r.ranking.map((fid) => [fid, r.finops[fid]?.total_tokens ?? 0]));
  const inTok = Object.fromEntries(r.ranking.map((fid) => [fid, r.finops[fid]?.input_tokens ?? 0]));
  const outTok = Object.fromEntries(r.ranking.map((fid) => [fid, r.finops[fid]?.output_tokens ?? 0]));
  const max = Math.max(...Object.values(vals), 1);
  const order = [...r.ranking].sort((a, b) => vals[a] - vals[b]);
  const rows = order.map((fid) => el("div", { class: "bar-row" }, [
    el("span", { class: "bar-label", text: r.names[fid] }),
    el("div", { class: "bar-track" }, el("div", {
      class: "bar-fill", style: `width:${(vals[fid] / max) * 100}%`,
      tip: `${r.names[fid]}: ${inTok[fid].toLocaleString()} in · ${outTok[fid].toLocaleString()} out · ${vals[fid].toLocaleString()} total`,
    })),
    el("span", { class: "bar-value", text: vals[fid] > 0 ? `${(vals[fid] / 1000).toFixed(0)}k` : "–" }),
  ]));
  return el("div", { class: "bars" }, rows);
}


async function loadRunList() {
  const mode = document.querySelector("input[name=results-mode]:checked").value;
  const sel = document.getElementById("run-select");
  const prev = sel.value;
  try {
    const r = await (await fetch(`/api/v1/run-list?mode=${mode}`)).json();
    sel.replaceChildren(new Option("All runs (aggregated)", ""));
    for (const run of r.runs) {
      sel.append(new Option(`${run.label}  (${run.file_count} files)`, run.id));
    }
    if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  } catch (_) { /* leave selector as-is on network error */ }
}

async function loadResults() {
  const mode = document.querySelector("input[name=results-mode]:checked").value;
  const run = document.getElementById("run-select").value;
  const url = run ? `/api/v1/results?mode=${mode}&run=${run}` : `/api/v1/results?mode=${mode}`;
  const res = await fetch(url);
  const r = await res.json();
  const ids = ["matrix", "ot", "ranking", "evidence", "finops", "sensitivity"];
  ids.forEach((id) => { const el = document.getElementById(id); if (el) el.replaceChildren(); });
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
  document.getElementById("sensitivity").append(renderSensitivity(r));
  document.getElementById("sens-meta").textContent = `(${r.sensitivity.samples} Dirichlet weight samples)`;
  bindTooltips(document.getElementById("results-card"));
}

document.querySelectorAll("input[name=results-mode]").forEach((i) => i.addEventListener("change", async () => {
  await loadRunList();
  loadResults();
}));
document.getElementById("run-select").addEventListener("change", loadResults);
