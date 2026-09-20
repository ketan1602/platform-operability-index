#!/usr/bin/env bash
# POI Benchmark — Local Monitoring Stack Bootstrap
# Target: OrbStack local Kubernetes
# Usage: ./install.sh [--context <kube-context>]
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."

# ---------------------------------------------------------------------------
# Source local .env if present (gitignored — never committed)
# ---------------------------------------------------------------------------
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  echo "[install] Sourcing ${SCRIPT_DIR}/.env"
  source "${SCRIPT_DIR}/.env"
fi

# ---------------------------------------------------------------------------
# Optional overrides from env vars (Vault injects these in CI)
# ---------------------------------------------------------------------------
KUBE_CONTEXT="${KUBE_CONTEXT:-orbstack}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-}"
PROM_NAMESPACE="poi-monitoring"
KYVERNO_NAMESPACE="kyverno"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
step() { echo; echo "━━━ $* ━━━"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

require_var() {
  local var="$1"
  [[ -n "${!var:-}" ]] || die "${var} must be set (see .env.example)"
}

kubectl_ctx() { kubectl --context "${KUBE_CONTEXT}" "$@"; }
helm_ctx()    { helm --kube-context "${KUBE_CONTEXT}" "$@"; }

# ---------------------------------------------------------------------------
# Parse CLI args
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --context) KUBE_CONTEXT="$2"; shift 2 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

echo "[install] Using kube context: ${KUBE_CONTEXT}"

# ---------------------------------------------------------------------------
# Step 1 — Namespaces
# ---------------------------------------------------------------------------
step "Step 1/5 — Creating namespaces"
kubectl_ctx apply -f "${SCRIPT_DIR}/namespaces.yaml"
echo "[install] Namespaces applied."

# ---------------------------------------------------------------------------
# Step 2 — kube-prometheus-stack
# ---------------------------------------------------------------------------
step "Step 2/5 — Installing kube-prometheus-stack"
helm_ctx repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm_ctx repo update

PROM_SET_ARGS=()
if [[ -n "${GRAFANA_ADMIN_PASSWORD}" ]]; then
  PROM_SET_ARGS+=(--set "grafana.adminPassword=${GRAFANA_ADMIN_PASSWORD}")
else
  echo "[install] WARNING: GRAFANA_ADMIN_PASSWORD not set — Grafana admin password will be auto-generated."
fi

helm_ctx upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace "${PROM_NAMESPACE}" \
  --create-namespace \
  --values "${SCRIPT_DIR}/monitoring/prometheus-values.yaml" \
  "${PROM_SET_ARGS[@]+"${PROM_SET_ARGS[@]}"}"

echo "[install] kube-prometheus-stack installed."

# ---------------------------------------------------------------------------
# Step 3 — Kyverno
# ---------------------------------------------------------------------------
step "Step 3/5 — Installing Kyverno"
helm_ctx repo add kyverno https://kyverno.github.io/kyverno/ 2>/dev/null || true
helm_ctx repo update

helm_ctx upgrade --install kyverno kyverno/kyverno \
  --namespace "${KYVERNO_NAMESPACE}" \
  --create-namespace

echo "[install] Kyverno installed."
echo "[install] Waiting for Kyverno webhook to be ready…"
kubectl_ctx rollout status deployment/kyverno \
  --namespace "${KYVERNO_NAMESPACE}" \
  --timeout=180s

# ---------------------------------------------------------------------------
# Step 4 — OTel Collector
# ---------------------------------------------------------------------------
step "Step 4/5 — Deploying OTel Collector"
kubectl_ctx apply -f "${SCRIPT_DIR}/otel-collector/configmap.yaml"
kubectl_ctx apply -f "${SCRIPT_DIR}/otel-collector/deployment.yaml"
echo "[install] OTel Collector manifests applied."

# ---------------------------------------------------------------------------
# Step 5 — Verify all pods
# ---------------------------------------------------------------------------
step "Step 5/5 — Verifying rollouts"

echo "[install] Verifying OTel Collector…"
kubectl_ctx rollout status deployment/otel-collector \
  --namespace "${PROM_NAMESPACE}" \
  --timeout=120s

echo "[install] Verifying kube-prometheus-stack operator…"
kubectl_ctx rollout status deployment/kube-prom-kube-prometheus-prometheus-operator \
  --namespace "${PROM_NAMESPACE}" \
  --timeout=180s || \
kubectl_ctx rollout status deployment/kube-prom-operator \
  --namespace "${PROM_NAMESPACE}" \
  --timeout=180s 2>/dev/null || \
echo "[install] WARNING: Could not find operator deployment by expected name — check manually."

echo
echo "✓ POI monitoring stack is ready."
echo "  OTel Collector  : otel-collector.${PROM_NAMESPACE}:4317 (gRPC), :4318 (HTTP)"
echo "  Prometheus      : kube-prom-kube-prometheus-prometheus.${PROM_NAMESPACE}:9090"
echo "  Grafana         : kube-prom-grafana.${PROM_NAMESPACE}:80"
echo
echo "  To port-forward Grafana:"
echo "    kubectl --context ${KUBE_CONTEXT} port-forward svc/kube-prom-grafana 3000:80 -n ${PROM_NAMESPACE}"
