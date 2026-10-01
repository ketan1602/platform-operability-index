#!/usr/bin/env bash
# Build and deploy POI mock servers to OrbStack K8s.
# Run once before ./infra.sh up; re-run whenever server code changes.
#
# Requires: docker, kubectl, OrbStack running
# Registry: localhost:5000 (OrbStack routes this from the K8s node)
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
cd "$SCRIPT_DIR"

KUBE_CONTEXT="${KUBE_CONTEXT:-orbstack}"
REGISTRY="${MOCK_REGISTRY:-localhost:5000}"
IMAGE="${REGISTRY}/poi-mock-servers:latest"
MANIFESTS="k8s/mock-servers"

die() { echo "error: $*" >&2; exit 1; }

# Ensure local registry is running
if ! curl -sf "http://${REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "Starting local Docker registry at ${REGISTRY}..."
  docker run -d -p 5000:5000 --name poi-registry --restart=always registry:2 2>/dev/null \
    || docker start poi-registry 2>/dev/null \
    || die "Could not start local registry — ensure Docker is running"
  sleep 3
fi

echo "Building mock server image (context: repo root)..."
docker build \
  -t "$IMAGE" \
  -f "${MANIFESTS}/Dockerfile" \
  --label "poi.built-at=$(date -u +%Y%m%dT%H%M%SZ)" \
  .

echo "Pushing ${IMAGE}..."
docker push "$IMAGE"

echo "Applying K8s manifests (context: ${KUBE_CONTEXT})..."
kubectl --context "$KUBE_CONTEXT" apply -f "${MANIFESTS}/namespace.yaml"
kubectl --context "$KUBE_CONTEXT" apply -f "${MANIFESTS}/"

echo "Waiting for rollout..."
for svc in mock-api mock-crm mock-approval ml-endpoint channel-adapter; do
  kubectl --context "$KUBE_CONTEXT" -n poi rollout status \
    deployment/"$svc" --timeout=120s
done

echo ""
echo "Mock servers deployed to namespace 'poi'."
echo "Now run: ./infra.sh up"
