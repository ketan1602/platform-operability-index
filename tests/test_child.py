"""The process supervisor: real subprocesses, real SIGKILL."""

from harness.shared import child, ledger


def _run(tmp_path, func, **watch):
    path = tmp_path / "ledger.jsonl"
    proc = child.spawn(f"tests.child_targets:{func}", {}, path)
    return child.watch(proc, path, **{"timeout_s": 30, **watch}), proc, path


def test_normal_exit_returns_result(tmp_path):
    out, _, _ = _run(tmp_path, "finish")
    assert out.stop == "exited" and out.result == {"stop": "final_answer"}


def test_holding_child_is_killed(tmp_path):
    out, proc, _ = _run(tmp_path, "hold")
    assert out.stop == "held" and proc.returncode == -9


def test_runaway_is_killed_at_ceiling(tmp_path):
    out, proc, path = _run(tmp_path, "runaway", ceiling=("tool", 5))
    assert out.stop == "ceiling" and proc.returncode == -9
    assert ledger.count(ledger.read(path), "tool") >= 5


def test_timeout_kills(tmp_path):
    out, proc, _ = _run(tmp_path, "runaway", timeout_s=1)
    assert out.stop == "timeout" and proc.returncode == -9


def test_exception_is_reported_not_raised(tmp_path):
    out, _, _ = _run(tmp_path, "boom")
    assert out.result["stop"] == "exception" and out.result["signal"] == "ValueError"


def test_ledger_record_requires_trial_env(monkeypatch):
    monkeypatch.delenv(ledger.LEDGER_ENV, raising=False)
    try:
        ledger.record("x")
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError outside a trial")
