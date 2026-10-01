"""Jaeger span analysis, custom-LOC counting, and UI progress-line parsing."""
import json

from api.routes.runs import _line_event, _total
from harness.shared import custom_loc, jaeger


def _span(sid, trace="t1", parent=None, name="invoke_agent supervisor", **tags):
    refs = [{"refType": "CHILD_OF", "traceID": trace, "spanID": parent}] if parent else []
    return {"traceID": trace, "spanID": sid, "operationName": name, "references": refs,
            "tags": [{"key": k.replace("__", "."), "value": v} for k, v in tags.items()]}


def test_connected_trace_with_legacy_provider_alias():
    spans = [
        _span("a", gen_ai__operation__name="invoke_agent", gen_ai__system="strands-agents"),
        _span("b", parent="a", name="execute_tool billing_agent", gen_ai__usage__input_tokens=5,
              gen_ai__usage__output_tokens=3),
    ]
    out = jaeger.analyse(spans, ["supervisor", "billing_agent"])
    assert out["trace_ids_per_run"] == 1 and out["orphan_spans"] == 0
    assert out["missing_required_attributes"] == [] and out["agents_traced"] == 2


def test_broken_trace_detected():
    out = jaeger.analyse([_span("a"), _span("b", trace="t2", parent="zzz")], ["supervisor", "network_agent"])
    assert out["trace_ids_per_run"] == 2 and out["orphan_spans"] == 1 and out["agents_traced"] == 1


def test_custom_loc_counts_only_fenced_code(tmp_path):
    f = tmp_path / "w.py"
    f.write_text("a = 1\n# poi:custom-begin\nb = 2\n\n# note\nc = 3\n# poi:custom-end\nd = 4\n")
    assert custom_loc.count(f) == 2


def test_progress_line_parsing():
    ev = _line_event("  OK   LangGraph       RLC idiomatic #3")
    payload = json.loads(ev.split("data: ", 1)[1])
    assert payload == {"ok": True, "framework": "LangGraph", "scenario": "RLC", "impl": "idiomatic",
                       "repeat": 3, "error": None}


def test_combo_total_mirrors_run_all():
    assert _total(["F1", "F2"], ["RLC", "GEW"], ["fixed", "idiomatic"], "live", 5) == 14
    assert _total(["F1"], ["RLC", "GEW"], ["fixed"], "dry_run", 5) == 1
