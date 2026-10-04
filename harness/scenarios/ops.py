"""P9 — Ops Experience measurement: FinOps, Runtime, and Fleet management.

Uses the DX SMOKE workload as a representative agent cycle to capture:
  - input_tokens_per_run:      LLM token overhead per single-agent run
  - agent_run_latency_ms:      end-to-end wall time for one complete cycle
  - concurrent_throughput_ratio: N=3 parallel runs vs N=1 sequential

cross_worker_resume is read from the AHQ trial result (stored in result_cache
after ahq.measure() runs). If AHQ has not run in this process, it stays None.
"""
from __future__ import annotations
import concurrent.futures
import threading
import time

import structlog

from harness.scenarios.common import env_int, impl_target, workdir
from harness.shared import child, ledger, result_cache
from harness.shared.pillar_models import P9Measurements

log = structlog.get_logger(__name__)


def _run_with_resources(fw: str, suffix: str) -> tuple[float, list[dict], float | None, float | None]:
    """Run the SMOKE workload; monitor child RSS + CPU in a background thread."""
    rss_samples: list[int] = []
    cpu_samples: list[float] = []
    stop_evt = threading.Event()

    def _poll(pid: int) -> None:
        try:
            import psutil
            p = psutil.Process(pid)
            while not stop_evt.wait(0.5):
                rss_samples.append(p.memory_info().rss)
                cpu_samples.append(p.cpu_percent())
        except Exception:
            pass

    path = workdir("OPS") / f"ledger_{suffix}.jsonl"
    t0 = time.monotonic()
    proc = child.spawn(impl_target("DX", fw), {"mistake": "SMOKE"}, path)
    poll_t = threading.Thread(target=_poll, args=(proc.pid,), daemon=True)
    poll_t.start()
    child.watch(proc, path, timeout_s=env_int("POI_OPS_TIMEOUT_S", 120))
    stop_evt.set()
    poll_t.join(timeout=2)

    peak_rss = round(max(rss_samples) / (1024 * 1024), 1) if rss_samples else None
    avg_cpu = round(sum(cpu_samples) / len(cpu_samples), 1) if cpu_samples else None
    return time.monotonic() - t0, ledger.read(path), peak_rss, avg_cpu


def _single_run(fw: str, suffix: str) -> tuple[float, list[dict]]:
    path = workdir("OPS") / f"ledger_{suffix}.jsonl"
    t0 = time.monotonic()
    proc = child.spawn(impl_target("DX", fw), {"mistake": "SMOKE"}, path)
    child.watch(proc, path, timeout_s=env_int("POI_OPS_TIMEOUT_S", 120))
    return time.monotonic() - t0, ledger.read(path)


def _concurrent_ratio(fw: str, n: int | None = None) -> float | None:
    """Throughput scaling: (N × seq_wall_s) / conc_wall_s; ≥ 1.0 means linear or better."""
    n = n or env_int("POI_OPS_CONCURRENCY", 3)
    seq_elapsed, _ = _single_run(fw, "seq")
    if seq_elapsed <= 0:
        return None

    def _one(i: int) -> None:
        path = workdir("OPS") / f"ledger_conc_{i}.jsonl"
        proc = child.spawn(impl_target("DX", fw), {"mistake": "SMOKE"}, path)
        child.watch(proc, path, timeout_s=env_int("POI_OPS_TIMEOUT_S", 120))

    t_start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        list(pool.map(_one, range(n)))
    conc_elapsed = time.monotonic() - t_start

    if conc_elapsed <= 0:
        return None
    return round((n * seq_elapsed) / conc_elapsed, 2)


def measure(fw: str) -> dict:
    elapsed_s, entries, peak_rss_mb, avg_cpu_pct = _run_with_resources(fw, "primary")
    tok = ledger.sum_tokens(entries)
    input_tokens = tok.get("input_tokens") or None
    ratio = _concurrent_ratio(fw)

    cross_worker = result_cache.load(fw, "resume_succeeded")
    m = P9Measurements(
        input_tokens_per_run=input_tokens,
        agent_run_latency_ms=int(elapsed_s * 1000),
        concurrent_throughput_ratio=ratio,
        cross_worker_resume=cross_worker,
        peak_rss_mb=peak_rss_mb,
        avg_cpu_percent=avg_cpu_pct,
    )
    log.info("p9.measured", fw=fw, input_tokens=input_tokens,
             latency_ms=m.agent_run_latency_ms, ratio=ratio,
             cross_worker=cross_worker, peak_rss_mb=peak_rss_mb, avg_cpu_pct=avg_cpu_pct)
    notes = (
        f"input_tokens={input_tokens} "
        f"latency_ms={m.agent_run_latency_ms} "
        f"concurrent_ratio={ratio} "
        f"cross_worker_resume={cross_worker} "
        f"peak_rss_mb={peak_rss_mb} avg_cpu%={avg_cpu_pct}"
    )
    return {"notes": notes, "p9": m}
