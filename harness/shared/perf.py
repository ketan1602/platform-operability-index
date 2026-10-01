"""Runtime performance metrics derived from the append-only ledger.

All metrics are computed post-hoc from timestamps already present in ledger
entries — no extra instrumentation required.
"""
from __future__ import annotations
from statistics import median


def cold_start_ms(entries: list[dict], spawn_ts: float) -> int | None:
    """Milliseconds from process spawn to first ledger entry (framework init overhead)."""
    if not entries:
        return None
    return int((entries[0]["ts"] - spawn_ts) * 1000)


def inter_tool_latency_ms(entries: list[dict], event: str) -> int | None:
    """Median ms between consecutive occurrences of *event* (LLM round-trip + routing)."""
    times = [e["ts"] for e in entries if e.get("event") == event]
    if len(times) < 2:
        return None
    gaps = [(times[i + 1] - times[i]) * 1000 for i in range(len(times) - 1)]
    return int(median(gaps))


def peak_memory_rss_mb(entries: list[dict]) -> float | None:
    """Peak RSS in MB recorded by any ledger entry (written by child process via psutil)."""
    vals = [e["mem_rss_mb"] for e in entries if "mem_rss_mb" in e]
    return round(max(vals), 1) if vals else None


def total_wall_ms(entries: list[dict]) -> int | None:
    """Total elapsed ms from first to last ledger entry."""
    times = [e["ts"] for e in entries]
    if len(times) < 2:
        return None
    return int((max(times) - min(times)) * 1000)


def summarise(entries: list[dict], spawn_ts: float, tool_event: str) -> dict:
    """Return all performance metrics in a single dict for embedding in result files."""
    return {
        "cold_start_ms": cold_start_ms(entries, spawn_ts),
        "inter_tool_latency_ms": inter_tool_latency_ms(entries, tool_event),
        "peak_memory_rss_mb": peak_memory_rss_mb(entries),
        "total_wall_ms": total_wall_ms(entries),
    }
