"""Cross-run aggregation: medians within a scenario, weakest link across scenarios."""
from analysis.aggregate import aggregate
from harness.shared.measurement import (FrameworkId, ImplementationType, Pillar, PillarScores,
                                        RunMetadata, RunResult, ScenarioId)


def _run(sc: str, fw: str = "F1", error: str | None = None, **scores) -> RunResult:
    meta = RunMetadata(framework_id=FrameworkId(fw), framework_version="t", scenario_id=ScenarioId(sc),
                       implementation_type=ImplementationType.IDIOMATIC, pillar=Pillar.ALL)
    raw = {p: {} for p in scores}
    return RunResult(run_metadata=meta, pillar_scores=PillarScores(**scores), raw_measurements=raw, error=error)


def test_median_within_scenario_and_min_across_scenarios():
    runs = [_run("RLC", p2=3), _run("RLC", p2=3), _run("RLC", p2=1), _run("SMA", p2=1), _run("SMA", p2=1)]
    f1 = aggregate(runs)["F1"]
    assert f1["evidence"]["p2"]["RLC"]["median"] == 3
    assert f1["evidence"]["p2"]["RLC"]["min"] == 1
    assert f1["scores"]["p2"] == 1  # weakest link: SMA


def test_inconclusive_repeats_excluded_but_counted():
    f1 = aggregate([_run("RLC", p2=None), _run("RLC", p2=2)])["F1"]
    assert f1["evidence"]["p2"]["RLC"] == {"median": 2, "min": 2, "max": 2, "n": 1, "inconclusive": 1}


def test_measured_evidence_replaces_baseline_for_p1_to_p3():
    f1 = aggregate([_run("GEW", p1=2, p4=2), _run("AHQ", p1=3, p4=2)])["F1"]
    assert f1["source"] == "measured"
    assert f1["scores"]["p1"] == 3          # AHQ only
    assert list(f1["evidence"]["p4"]) == ["GEW", "AHQ"]  # static pillars use every scenario


def test_baseline_only_framework_keeps_baseline_scores():
    f2 = aggregate([_run("GEW", fw="F2", p1=0, p2=1)])["F2"]
    assert f2["source"] == "baseline" and f2["scores"]["p1"] == 0 and f2["scores"]["p2"] == 1


def test_failed_runs_are_excluded():
    f1 = aggregate([_run("AHQ", p1=3), _run("AHQ", p1=0, error="LLM 500")])["F1"]
    assert f1["evidence"]["p1"]["AHQ"]["n"] == 1 and f1["scores"]["p1"] == 3
