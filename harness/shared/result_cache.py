"""In-process cache for cross-pillar evidence sharing.

AHQ stores its resume evidence so that OPS (cross_worker_resume) and the
LangGraph P1 GEW fallback (concurrent_resume_collision) can read it without
re-running the AHQ trial. Keyed by framework_id ('F1'..'F5').
"""
from __future__ import annotations

_STORE: dict[str, dict] = {}


def store(fw: str, key: str, value) -> None:
    _STORE.setdefault(fw, {})[key] = value


def load(fw: str, key: str, default=None):
    return _STORE.get(fw, {}).get(key, default)
