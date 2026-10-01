// Run controls, preflight status, and SSE streaming. Rendering helpers live in results.js.
const FRAMEWORKS = { F1: "LangGraph", F2: "AutoGen (MS)", F3: "OpenAI SDK", F4: "Google ADK", F5: "Strands" };
let source = null;
let done = 0;
let total = 0;

const $ = (id) => document.getElementById(id);
const checked = (name) => [...document.querySelectorAll(`input[name=${name}]:checked`)].map((i) => i.value);

function chip(label, state, tip) {
  const icon = { success: "✓", warning: "!", error: "✕" }[state];
  return el("span", { class: `status status-${state}`, text: `${icon} ${label}`, tip });
}

async function loadPreflight() {
  const r = await (await fetch("/health/ready")).json();
  const mocks = Object.entries(r.mock_services);
  const up = mocks.filter(([, v]) => v === "up").length;
  const fws = Object.entries(r.frameworks_installed);
  const installed = fws.filter(([, v]) => v).length;
  const missingFw = fws.filter(([, v]) => !v).map(([k]) => FRAMEWORKS[k]);
  $("preflight").replaceChildren(
    chip("LLM credentials", r.llm_env_missing.length ? "error" : "success",
      r.llm_env_missing.length ? `Missing: ${r.llm_env_missing.join(", ")}` : "AI Refinery env vars set"),
    chip(`Services ${up}/${mocks.length}`, up === mocks.length ? "success" : "error",
      mocks.map(([k, v]) => `${k}: ${v}`).join(" · ")),
    chip(`Frameworks ${installed}/${fws.length}`, installed === fws.length ? "success" : "warning",
      missingFw.length ? `No venv (run ./setup_venvs.sh): ${missingFw.join(", ")}` : "All adapter venvs present"),
  );
  bindTooltips($("preflight"));
}

function renderFrameworkChecks() {
  $("fw-checks").replaceChildren(...Object.entries(FRAMEWORKS).map(([id, name]) =>
    el("label", {}, [el("input", { type: "checkbox", name: "fw", value: id, checked: "" }), ` ${name}`])));
}

const MEASURED = ["RLC", "SMA", "AHQ"];

function comboCount() {
  const live = document.querySelector("input[name=mode]:checked").value === "live";
  const reps = Number($("repeats").value) || 1;
  const perFw = checked("scenario").reduce((n, sc) =>
    n + (MEASURED.includes(sc) ? (live ? reps : 0) : checked("impl").length), 0);
  return checked("fw").length * perFw;
}

function updateCount() {
  const n = comboCount();
  $("combo-count").textContent = `${n} combination${n === 1 ? "" : "s"}`;
  $("run-btn").disabled = n === 0 || source !== null;
}

function setProgress() {
  $("progress-bar").style.width = total ? `${(done / total) * 100}%` : "0";
  $("run-status").textContent = total ? `${done} / ${total} combinations complete` : "";
}

function appendLog(line) {
  const log = $("log");
  log.textContent += `${line}\n`;
  log.scrollTop = log.scrollHeight;
}

function addCombo(c) {
  const state = c.ok ? "success" : "error";
  const label = `${c.framework} · ${c.scenario} · ${c.impl} · #${c.repeat}`;
  const children = [el("span", { class: `status status-${state}`, text: c.ok ? "✓ OK" : "✕ FAIL" }),
    el("span", { text: ` ${label}` })];
  if (c.error) children.push(el("span", { class: "combo-error", text: c.error }));
  $("combo-list").append(el("li", {}, children));
  done += 1;
  setProgress();
}

function finish(message) {
  if (source) source.close();
  source = null;
  $("stop-btn").disabled = true;
  if (message) $("run-status").textContent = message;
  updateCount();
}

function startRun() {
  const mode = document.querySelector("input[name=mode]:checked").value;
  const qs = new URLSearchParams({ frameworks: checked("fw").join(","),
    scenarios: checked("scenario").join(","), impls: checked("impl").join(","), mode,
    repeats: $("repeats").value });
  done = 0; total = 0;
  $("combo-list").replaceChildren();
  $("log").textContent = "";
  setProgress();
  source = new EventSource(`/api/v1/runs/stream?${qs}`);
  $("run-btn").disabled = true;
  $("stop-btn").disabled = false;
  source.addEventListener("start", (e) => {
    const d = JSON.parse(e.data);
    total = d.total;
    setProgress();
    appendLog(`[run ${d.run_id}] mode=${d.mode} combos=${d.total}`);
  });
  source.addEventListener("log", (e) => appendLog(JSON.parse(e.data).line));
  source.addEventListener("combo", (e) => addCombo(JSON.parse(e.data)));
  source.addEventListener("fatal", (e) => finish(`✕ ${JSON.parse(e.data).error}`));
  source.addEventListener("done", (e) => {
    const code = JSON.parse(e.data).exit_code;
    finish(code === 0 ? `✓ All ${total} combinations passed` : `✕ Finished with failures (exit ${code})`);
    document.querySelector(`input[name=results-mode][value=${mode}]`).checked = true;
    loadResults();
  });
  source.onerror = () => { if (source) finish("✕ Connection to server lost"); };
}

$("run-btn").addEventListener("click", startRun);
$("stop-btn").addEventListener("click", () => finish("Run stopped — the server has killed the benchmark process."));
document.querySelectorAll("#run-card input[type=checkbox], #run-card input[name=mode]")
  .forEach((i) => i.addEventListener("change", updateCount));
$("repeats").addEventListener("input", updateCount);
renderFrameworkChecks();
document.querySelectorAll("#fw-checks input").forEach((i) => i.addEventListener("change", updateCount));
updateCount();
loadPreflight();
loadResults();
