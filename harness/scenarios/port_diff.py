"""Compute reuse rates across the full SMA cross-framework port matrix."""
from __future__ import annotations
import difflib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

_IMPL_DIRS = {
    "F1": "langgraph",
    "F2": "ms_agent",
    "F3": "openai_agents_sdk",
    "F4": "google_adk",
    "F5": "strands_agents",
}
_PORT_DIR_NAME = {
    "F1": "ported_from_langgraph",
    "F2": "ported_from_autogen",
    "F3": "ported_from_openai_sdk",
    "F4": "ported_from_google_adk",
    "F5": "ported_from_strands",
}
_IDIOMATIC = "scenarios/sma/implementations/{impl_dir}/idiomatic/workflow.py"
_PORT_PATH = "scenarios/sma/implementations/{impl_dir}/{port_dir}/workflow.py"

# All 5 frameworks are both sources and targets (full 5×4 matrix).
_SOURCES: dict[str, list[str]] = {
    "F1": ["F2", "F3", "F4", "F5"],
    "F2": ["F1", "F3", "F4", "F5"],
    "F3": ["F1", "F2", "F4", "F5"],
    "F4": ["F1", "F2", "F3", "F5"],
    "F5": ["F1", "F2", "F3", "F4"],
}


def _code_lines(path: Path) -> list[str]:
    """Non-blank, non-comment lines stripped of trailing whitespace."""
    return [
        ln.rstrip() for ln in path.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith(("#", '"""', "'''"))
    ]


def compute_reuse(source: Path, target: Path) -> dict:
    src = _code_lines(source)
    tgt = _code_lines(target)
    matcher = difflib.SequenceMatcher(None, src, tgt, autojunk=False)
    matching = sum(b.size for b in matcher.get_matching_blocks())
    total = max(len(src), len(tgt))
    changed = total - matching
    return {
        "source_lines": len(src),
        "target_lines": len(tgt),
        "matching_lines": matching,
        "changed_lines": changed,
        "reuse_rate": round(matching / total, 3) if total else 0.0,
        "entanglement_ratio": round(changed / total, 3) if total else 1.0,
    }


def port_metrics() -> dict[str, dict]:
    """Return per-source-framework metrics averaged across all 4 target ports.

    Shape: {fw_id: {"avg_reuse_rate": float, "avg_changed_lines": int, "by_target": {fw_id: dict}}}
    """
    result: dict[str, dict] = {}
    for src_fw, targets in _SOURCES.items():
        src_path = _ROOT / _IDIOMATIC.format(impl_dir=_IMPL_DIRS[src_fw])
        if not src_path.exists():
            continue
        by_target: dict[str, dict] = {}
        for tgt_fw in targets:
            port_path = _ROOT / _PORT_PATH.format(
                impl_dir=_IMPL_DIRS[tgt_fw],
                port_dir=_PORT_DIR_NAME[src_fw],
            )
            if port_path.exists():
                by_target[tgt_fw] = compute_reuse(src_path, port_path)
        if not by_target:
            continue
        vals = list(by_target.values())
        avg_reuse = round(sum(v["reuse_rate"] for v in vals) / len(vals), 3)
        avg_changed = round(sum(v["changed_lines"] for v in vals) / len(vals))
        result[src_fw] = {
            "avg_reuse_rate": avg_reuse,
            "avg_changed_lines": avg_changed,
            "by_target": by_target,
        }
    return result
