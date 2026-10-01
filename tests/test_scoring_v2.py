"""Scoring rules for measured (RLC/SMA/AHQ) evidence, and the dispatch that routes to them."""
from harness.shared.pillar_models import P1Measurements, P2Measurements, P3Measurements
from harness.shared.scoring import score_p1, score_p2, score_p3

CLEAN_RESUME = dict(resume_succeeded=True, state_intact_after_kill=True, steps_re_executed_on_resume=0,
                    side_effect_executions=1, custom_code_lines_to_reach_score_3=0)


def test_p1_native_safe_resume_scores_3():
    assert score_p1(P1Measurements(**CLEAN_RESUME)) == 3


def test_p1_duplicate_side_effect_under_concurrent_resume_caps_at_2():
    assert score_p1(P1Measurements(**{**CLEAN_RESUME, "side_effect_executions": 2})) == 2


def test_p1_custom_persistence_caps_at_2():
    assert score_p1(P1Measurements(**{**CLEAN_RESUME, "custom_code_lines_to_reach_score_3": 19})) == 2


def test_p1_lossy_resume_scores_1():
    assert score_p1(P1Measurements(**{**CLEAN_RESUME, "state_intact_after_kill": False})) == 1
    assert score_p1(P1Measurements(**{**CLEAN_RESUME, "steps_re_executed_on_resume": 1})) == 1


def test_p1_failed_resume_scores_0():
    assert score_p1(P1Measurements(**{**CLEAN_RESUME, "resume_succeeded": False})) == 0


def test_p1_legacy_path_unchanged_when_no_resume_evidence():
    m = P1Measurements(checkpoint_format="parseable", duplicate_tool_calls_on_mid_write=0)
    assert score_p1(m) == 2


def test_p2_loop_typed_default_halt_scores_3():
    m = P2Measurements(loop_halted_by_framework=True, halt_signal_structured=True, model_self_terminated=False)
    assert score_p2(m) == 3


def test_p2_loop_untyped_halt_scores_2():
    m = P2Measurements(loop_halted_by_framework=True, halt_signal_structured=False, model_self_terminated=False)
    assert score_p2(m) == 2


def test_p2_loop_only_configured_limit_scores_2_else_platform_kill_1():
    base = dict(loop_halted_by_framework=False, model_self_terminated=False)
    assert score_p2(P2Measurements(**base, configured_limit_honored=True)) == 2
    assert score_p2(P2Measurements(**base, configured_limit_honored=False)) == 1


def test_p2_model_self_termination_is_inconclusive():
    m = P2Measurements(loop_halted_by_framework=False, model_self_terminated=True, configured_limit_honored=True)
    assert score_p2(m) is None


def test_p2_isolation_outcomes():
    assert score_p2(P2Measurements(failure_propagation="contained")) == 3
    assert score_p2(P2Measurements(failure_propagation="crashed_run")) == 1
    assert score_p2(P2Measurements(failure_propagation="hung")) == 0


def test_p3_trace_rules():
    good = dict(framework_spans=30, missing_required_attributes=[], trace_ids_per_run=1, orphan_spans=0,
                agents_invoked=4, agents_traced=4, custom_exporter_loc=0)
    assert score_p3(P3Measurements(**good)) == 3
    assert score_p3(P3Measurements(**{**good, "trace_ids_per_run": 5})) == 2
    assert score_p3(P3Measurements(**{**good, "missing_required_attributes": ["gen_ai.usage.input_tokens"]})) == 1
    assert score_p3(P3Measurements(**{**good, "framework_spans": 0})) == 0
