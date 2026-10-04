"""SEC infrastructure-level security checks — K8s RBAC, admission control, HTTP bleed.

Extracted from sec.py to keep that module within the 150-line budget.
D and E require `./deploy/setup-poi-sec.sh` to have been run against the cluster.
"""
from __future__ import annotations
import os
import subprocess
import uuid
from pathlib import Path

import requests
import structlog

from harness.scenarios.common import TrialError, env_int, impl_target
from harness.shared import child, jaeger, ledger
from scenarios.sec.shared.tools import BLEED_TOKEN_ENV, MOCK_AUTH_URL_ENV

log = structlog.get_logger(__name__)
_K8S_TIMEOUT = "POI_SEC_K8S_TIMEOUT_S"
_SEC_TIMEOUT = "POI_SEC_TIMEOUT_S"
_KUBE_CONTEXT = os.environ.get("KUBE_CONTEXT", "orbstack")
_K8S_DIR = Path(os.environ.get(
    "POI_SEC_K8S_DIR",
    str(Path(__file__).resolve().parents[3] / "platform" / "k8s" / "poi-sec"),
))


def _run_k8s_probe(template: Path) -> bool:
    """Apply a probe Job, wait for completion, clean up, return True=PASS."""
    job_name = f"{template.stem}-{uuid.uuid4().hex[:8]}"
    namespace = "poi-sec-test"
    yml = template.read_text().replace(template.stem, job_name)
    kc = ["kubectl", f"--context={_KUBE_CONTEXT}"]
    subprocess.run([*kc, "apply", "-f", "-"], input=yml, text=True,
                   check=True, capture_output=True)
    try:
        r = subprocess.run(
            [*kc, "wait", "--for=condition=complete",
             f"--timeout={env_int(_K8S_TIMEOUT, 60)}s",
             f"job/{job_name}", f"-n={namespace}"],
            capture_output=True, text=True,
        )
        return r.returncode == 0
    finally:
        subprocess.run(
            [*kc, "delete", "job", job_name, f"-n={namespace}", "--ignore-not-found"],
            capture_output=True,
        )


def check_k8s_scope() -> bool:
    """PASS if K8s RBAC blocks poi-sec-probe from reading a cross-namespace secret."""
    template = _K8S_DIR / "jobs" / "scope-probe.yaml"
    if not template.exists():
        raise TrialError(f"K8s probe not found at {template} — run setup-poi-sec.sh first")
    return _run_k8s_probe(template)


def check_admission_control() -> bool:
    """PASS if Kyverno blocks privileged pod creation in poi-sec-test."""
    template = _K8S_DIR / "jobs" / "admission-probe.yaml"
    if not template.exists():
        raise TrialError(f"K8s probe not found at {template} — run setup-poi-sec.sh first")
    return _run_k8s_probe(template)


def check_trace_spans_clean(fw: str, wd: Path) -> bool | None:
    """PASS if no raw HTTP LLM spans appear without gen-ai semantic attributes.

    Runs the span_hygiene sub-test with OTEL enabled; fetches spans from Jaeger.
    Returns None when JAEGER_QUERY_URL or OTEL_EXPORTER_OTLP_ENDPOINT is not set.
    """
    otel_ep = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not os.environ.get("JAEGER_QUERY_URL") or not otel_ep:
        return None
    service = f"poi-{fw.lower()}-sec-spans-{uuid.uuid4().hex[:8]}"
    path = wd / "ledger_span_hygiene.jsonl"
    env = {"OTEL_SERVICE_NAME": service, "OTEL_EXPORTER_OTLP_ENDPOINT": otel_ep}
    proc = child.spawn(impl_target("SEC", fw), {"sub_test": "span_hygiene"}, path, env=env)
    child.watch(proc, path, timeout_s=env_int(_SEC_TIMEOUT, 300))
    spans = jaeger.fetch_spans(service)
    if not spans:
        return None
    return jaeger.spans_clean(spans)


def check_http_bleed(fw: str, wd: Path) -> int | None:
    """Run the HTTP bleed sub-test; return count of leaked-token events.

    Injects POI_BLEED_TOKEN into the child process then queries the mock auth
    server to count requests that carried that token.
    Returns None when MOCK_AUTH_URL is not set (infra not available).
    """
    base = os.environ.get(MOCK_AUTH_URL_ENV, "")
    if not base:
        log.info("http_bleed.skip", reason="MOCK_AUTH_URL not set")
        return None
    token = f"poi-bleed-{uuid.uuid4().hex[:12]}"
    try:
        requests.delete(f"{base}/bleed/events", timeout=5)
    except requests.RequestException as exc:
        log.warning("http_bleed.clear_failed", error=str(exc))
        return None
    path = wd / "ledger_bleed.jsonl"
    proc = child.spawn(impl_target("SEC", fw), {"sub_test": "bleed"}, path,
                       env={BLEED_TOKEN_ENV: token, MOCK_AUTH_URL_ENV: base})
    out = child.watch(proc, path, timeout_s=env_int(_SEC_TIMEOUT, 300))
    entries = ledger.read(path)  # noqa: F841 — may be useful for callers later
    if out.stop != "exited":
        log.warning("http_bleed.trial_failed", fw=fw, stop=out.stop)
        return None
    try:
        resp = requests.get(f"{base}/bleed/events", params={"token": token}, timeout=5)
        return int(resp.json().get("count", 0))
    except requests.RequestException as exc:
        log.warning("http_bleed.query_failed", error=str(exc))
        return None
