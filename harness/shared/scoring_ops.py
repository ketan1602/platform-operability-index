"""P9 — Ops Experience scoring (FinOps + Runtime + Fleet management)."""
from __future__ import annotations

from harness.shared.pillar_models import P9Measurements


def p9_from_ops(m: P9Measurements) -> int:
    """P9 — Ops Experience: FinOps + Runtime + Fleet (0-3).

    FinOps (weight 40%): input_tokens_per_run
        < 3 000  → 1.0   lean token budget
        < 10 000 → 0.5   moderate overhead
        else     → 0.0   heavy overhead

    Runtime (weight 30%): agent_run_latency_ms
        < 5 000ms  → 1.0  fast end-to-end tool cycle
        < 15 000ms → 0.5  acceptable
        else       → 0.0  slow / blocking

    Fleet (weight 30%): concurrent_throughput_ratio + cross_worker_resume
        ratio ≥ 0.8 AND resume → 1.0
        either passing → 0.5
        neither → 0.0

    Final = round(weighted × 3), clipped [0, 3].
    """
    tok = m.input_tokens_per_run
    if tok is None:
        finops_sub = 0.0
    elif tok < 3000:
        finops_sub = 1.0
    elif tok < 10000:
        finops_sub = 0.5
    else:
        finops_sub = 0.0

    lat = m.agent_run_latency_ms
    if lat is None:
        runtime_sub = 0.0
    elif lat < 5000:
        runtime_sub = 1.0
    elif lat < 15000:
        runtime_sub = 0.5
    else:
        runtime_sub = 0.0

    ratio = m.concurrent_throughput_ratio
    resume = m.cross_worker_resume
    if ratio is not None and ratio >= 0.8 and resume:
        fleet_sub = 1.0
    elif (ratio is not None and ratio >= 0.5) or resume:
        fleet_sub = 0.5
    else:
        fleet_sub = 0.0

    weighted = finops_sub * 0.40 + runtime_sub * 0.30 + fleet_sub * 0.30
    return min(round(weighted * 3), 3)
