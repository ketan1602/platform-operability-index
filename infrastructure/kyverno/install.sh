#!/usr/bin/env bash
# POI Benchmark — Kyverno Install + Policy Application
# Usage: ./install.sh [--context <kube-context>]
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."

# ---------------------------------------------------------------------------
# Source local .env if present (gitignored — never committed)
# ---------------------------------------------------------------------------
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  echo "[kyverno-install] Sourcing ${SCRIPT_DIR}/.env"
  source "${SCRIPT_DIR}/.env"
fi

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KUBE_CONTEXT="${KUBE_CONTEXT:-orbstack}"
KYVERNO_NAMESPACE="kyverno"
KYVERNO_VERSION="${KYVERNO_VERSION:-3.2.0}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
step() { echo; echo "━━━ $* ━━━"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

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

echo "[kyverno-install] Using kube context: ${KUBE_CONTEXT}"

# ---------------------------------------------------------------------------
# Step 1 — Add Kyverno Helm repo
# ---------------------------------------------------------------------------
step "Step 1/4 — Adding Kyverno Helm repo"
helm_ctx repo add kyverno https://kyverno.github.io/kyverno/ 2>/dev/null || true
helm_ctx repo update
echo "[kyverno-install] Helm repo ready."

# ---------------------------------------------------------------------------
# Step 2 — Install Kyverno
# ---------------------------------------------------------------------------
step "Step 2/4 — Installing Kyverno ${KYVERNO_VERSION}"
helm_ctx upgrade --install kyverno kyverno/kyverno \
  --namespace "${KYVERNO_NAMESPACE}" \
  --create-namespace \
  --version "${KYVERNO_VERSION}" \
  --set admissionController.replicas=1 \
  --set backgroundController.enabled=false \
  --wait

echo "[kyverno-install] Kyverno installed."

# ---------------------------------------------------------------------------
# Step 3 — Wait for webhook to be ready
# ---------------------------------------------------------------------------
step "Step 3/4 — Waiting for Kyverno admission controller"
kubectl_ctx rollout status deployment/kyverno-admission-controller \
  --namespace "${KYVERNO_NAMESPACE}" \
  --timeout=180s || \
kubectl_ctx rollout status deployment/kyverno \
  --namespace "${KYVERNO_NAMESPACE}" \
  --timeout=180s
echo "[kyverno-install] Webhook ready."

# ---------------------------------------------------------------------------
# Step 4 — Apply all ClusterPolicies
# ---------------------------------------------------------------------------
step "Step 4/4 — Applying ClusterPolicies"
kubectl_ctx apply -f "${SCRIPT_DIR}/policies/"
echo "[kyverno-install] All policies applied."

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
echo
echo "[kyverno-install] Active ClusterPolicies:"
kubectl_ctx get clusterpolicies -o wide

echo
echo "✓ Kyverno installed and POI policies are active."
