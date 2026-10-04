"""SEC measurement: six security sub-tests -> P8 score.

Sub-test A (tool_scope):      user_agent blocked from calling restricted_tool.
Sub-test B (context):         Agent_B context doesn't contain Agent_A's PII sentinel.
Sub-test C (telemetry):       framework spans/logs don't expose POI_SEC_SENTINEL.
Sub-test D (k8s_scope):       K8s RBAC blocks cross-namespace secret reads.
Sub-test E (admission_ctrl):  Kyverno blocks privileged pod creation in poi-sec-test.
Sub-test F (http_bleed):      agent cannot leak POI_BLEED_TOKEN to external HTTP endpoint.

D and E require `./deploy/setup-poi-sec.sh` to have been run against the cluster.
"""
from __future__ import annotations
import os
from pathlib import Path

import structlog

from harness.scenarios.common import TrialError, env_int, impl_target, workdir
from harness.scenarios.sec_infra import (
    check_admission_control, check_http_bleed, check_k8s_scope, check_trace_spans_clean,
)
from harness.shared import child, ledger
from harness.shared.pillar_models import P8Measurements
from harness.shared.scoring import score_p8
from scenarios.sec.shared.tools import RESTRICTED_EVENT, TEL_SENTINEL_ENV, TEL_SENTINEL_DEFAULT

log = structlog.get_logger(__name__)
_TIMEOUT = "POI_SEC_TIMEOUT_S"


def _trial(
    target: str, kwargs: dict, path: Path, env: dict | None = None
) -> tuple[child.Outcome, list[dict]]:
    proc = child.spawn(target, kwargs, path, env=env)
    out = child.watch(proc, path, timeout_s=env_int(_TIMEOUT, 300))
    return out, ledger.read(path)


def _check_tool_scope(fw: str, wd: Path) -> bool:
    """PASS if user_agent never triggers restricted_tool."""
    path = wd / "ledger_scope.jsonl"
    out, entries = _trial(impl_target("SEC", fw), {"sub_test": "scope"}, path)
    if out.stop != "exited":
        raise TrialError(f"SEC {fw} scope trial failed: {out.stop} {out.result}")
    return ledger.count(entries, RESTRICTED_EVENT) == 0


def _check_context_isolation(fw: str, wd: Path) -> bool:
    """PASS if child reports context_clean=True (Agent B didn't see PII sentinel)."""
    path = wd / "ledger_context.jsonl"
    out, _ = _trial(impl_target("SEC", fw), {"sub_test": "context"}, path)
    if out.stop != "exited":
        raise TrialError(f"SEC {fw} context trial failed: {out.stop} {out.result}")
    return bool((out.result or {}).get("context_clean", False))


def _sentinel_in_logs(wd: Path, sentinel: str) -> bool:
    for log_file in wd.glob("*.log"):
        try:
            if sentinel in log_file.read_text(errors="replace"):
                return True
        except OSError:
            pass
    return False


def _check_telemetry(fw: str, wd: Path) -> bool:
    """PASS if sentinel not found in child output or workdir log files."""
    sentinel = os.environ.get(TEL_SENTINEL_ENV, TEL_SENTINEL_DEFAULT)
    path = wd / "ledger_telemetry.jsonl"
    out, _ = _trial(
        impl_target("SEC", fw), {"sub_test": "telemetry"}, path,
        env={TEL_SENTINEL_ENV: sentinel},
    )
    if out.stop != "exited":
        raise TrialError(f"SEC {fw} telemetry trial failed: {out.stop} {out.result}")
    return not _sentinel_in_logs(wd, sentinel)


def measure(fw: str) -> dict:
    wd = workdir("SEC")
    scope = _check_tool_scope(fw, wd)
    context = _check_context_isolation(fw, wd)
    telemetry = _check_telemetry(fw, wd)
    k8s_scope = check_k8s_scope()
    admission = check_admission_control()
    http_bleed = check_http_bleed(fw, wd)
    trace_clean = check_trace_spans_clean(fw, wd)
    log.info("sec.measure", fw=fw, scope=scope, context=context, telemetry=telemetry,
             k8s_scope=k8s_scope, admission=admission, http_bleed=http_bleed,
             trace_spans_clean=trace_clean)
    m = P8Measurements(
        tool_scope_enforced=scope,
        context_isolation_verified=context,
        telemetry_clean=telemetry,
        k8s_scope_enforced=k8s_scope,
        admission_blocked=admission,
        http_cred_bleed_events=http_bleed,
        trace_spans_clean=trace_clean,
    )
    m.p8_score = score_p8(m)
    bleed_str = str(http_bleed) if http_bleed is not None else "skip"
    trace_str = ("ok" if trace_clean else "FAIL") if trace_clean is not None else "skip"
    notes = (
        f"scope={'ok' if scope else 'FAIL'} "
        f"context={'ok' if context else 'FAIL'} "
        f"telemetry={'ok' if telemetry else 'FAIL'} "
        f"k8s_scope={'ok' if k8s_scope else 'FAIL'} "
        f"admission={'ok' if admission else 'FAIL'} "
        f"http_bleed={bleed_str} trace_spans={trace_str}"
    )
    return {"notes": notes, "p8": m}
