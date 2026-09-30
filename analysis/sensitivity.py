"""Ranking stability under random pillar weights (Dirichlet alpha=1)."""
from __future__ import annotations
import random

PILLARS = ("p1", "p2", "p3", "p4", "p5")


def _tag(pct: int) -> str:
    if pct >= 80:
        return "stable"
    return "contested" if pct >= 60 else "fragile"


def compute_sensitivity(matrix: dict, n: int = 1000, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    fids = sorted(matrix)
    vecs = {f: [matrix[f].get(p, 0) for p in PILLARS] for f in fids}
    eq_order = sorted(fids, key=lambda f: (-matrix[f]["poi_total"], f))
    pairs = list(zip(eq_order, eq_order[1:]))
    wins = dict.fromkeys(pairs, 0)
    rank_hold = 0

    for _ in range(n):
        raw = [rng.gammavariate(1, 1) for _ in PILLARS]
        total = sum(raw)
        ws = {f: sum(r / total * s for r, s in zip(raw, vecs[f])) for f in fids}
        if sorted(fids, key=lambda f: (-ws[f], f)) == eq_order:
            rank_hold += 1
        for a, b in pairs:
            wins[(a, b)] += ws[a] > ws[b]

    rows = []
    for (a, b), w in wins.items():
        pct = round(w / n * 100)
        rows.append({"a": a, "b": b, "pct": pct, "tag": _tag(pct)})
    return {"samples": n, "pairs": rows, "full_rank_hold_pct": round(rank_hold / n * 100)}
