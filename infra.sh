#!/usr/bin/env bash
# Bring up the real backing services the live POI scenarios use.
#   ./infra.sh up | down | status
# Postgres, Neo4j, RabbitMQ: port-forwarded from the K8s cluster (works under STRICT mTLS).
# Jaeger: the Istio tracing addon in istio-system (infrastructure/jaeger/jaeger.yaml), port-forwarded.
# Stubs that stay stubs (GEW mocks, TCW ML + channel): local uvicorn processes.
# Credentials are read from the cluster's K8s secrets into .env.infra (gitignored, 0600).
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
cd "$SCRIPT_DIR"
if [[ -f ".env" ]]; then set -a; source ".env"; set +a; fi

KUBE_CONTEXT="${KUBE_CONTEXT:-orbstack}"
NS="${POI_INFRA_NAMESPACE:-platform}"
TRACING_NS="${POI_TRACING_NAMESPACE:-istio-system}"
OTLP_PORT="${POI_OTLP_LOCAL_PORT:-14318}"
JAEGER_UI_PORT="${POI_JAEGER_LOCAL_PORT:-16686}"
PG_PORT="${POI_PG_LOCAL_PORT:-15432}"
NEO4J_PORT="${POI_NEO4J_LOCAL_PORT:-17687}"
AMQP_PORT="${POI_AMQP_LOCAL_PORT:-15673}"
PG_DB="${POI_PG_DATABASE:-poi}"
STATE=".infra"
KC=(kubectl --context "$KUBE_CONTEXT" -n "$NS")

die() { echo "error: $*" >&2; exit 1; }
secret() { "${KC[@]}" get secret "$1" -o "jsonpath={.data.$2}" | base64 -d; }
urlenc() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.stdin.read(),safe=""))'; }

bg() {  # bg <name> <cmd...> — start a background process, remember its pid
  local name="$1"; shift
  if [[ -f "$STATE/$name.pid" ]] && kill -0 "$(cat "$STATE/$name.pid")" 2>/dev/null; then return; fi
  nohup "$@" >"$STATE/$name.log" 2>&1 &
  echo $! >"$STATE/$name.pid"
}

pf() {  # pf <name> <namespace> <svc> <local:remote> — port-forward that survives dropped connections
  bg "$1" bash -c "while true; do kubectl --context '$KUBE_CONTEXT' -n '$2' port-forward svc/$3 $4; sleep 1; done"
}

wait_port() {
  for _ in $(seq 1 30); do nc -z 127.0.0.1 "$1" 2>/dev/null && return; sleep 1; done
  die "port $1 ($2) did not open — see $STATE/$2.log"
}

write_env() {
  local pg_user pg_pass neo_auth rmq_user rmq_pass
  pg_user=$(secret postgres-secret POSTGRES_USER)
  pg_pass=$(secret postgres-secret POSTGRES_PASSWORD | urlenc)
  neo_auth=$(secret neo4j-secret NEO4J_AUTH)
  rmq_user=$("${KC[@]}" get deploy rabbitmq -o \
    'jsonpath={.spec.template.spec.containers[0].env[?(@.name=="RABBITMQ_DEFAULT_USER")].value}')
  rmq_pass=$(secret rabbitmq-credentials rabbitmq-pass | urlenc)
  [[ -n "$pg_user" && -n "$neo_auth" && -n "$rmq_user" ]] || die "could not read cluster credentials"
  umask 077
  cat >.env.infra <<EOF
POSTGRES_URL=postgresql://${pg_user}:${pg_pass}@127.0.0.1:${PG_PORT}/${PG_DB}
NEO4J_URI=bolt://127.0.0.1:${NEO4J_PORT}
NEO4J_USER=${neo_auth%%/*}
NEO4J_PASSWORD=${neo_auth#*/}
RABBITMQ_URL=amqp://${rmq_user}:${rmq_pass}@127.0.0.1:${AMQP_PORT}/%2F
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:${OTLP_PORT}
JAEGER_QUERY_URL=http://127.0.0.1:${JAEGER_UI_PORT}
MOCK_API_URL=http://127.0.0.1:8001
MOCK_CRM_URL=http://127.0.0.1:8002
APPROVAL_URL=http://127.0.0.1:8003
ML_ENDPOINT_URL=http://127.0.0.1:8102
CHANNEL_ADAPTER_URL=http://127.0.0.1:8103
EOF
}

ensure_database() {  # idempotent: create the dedicated benchmark database if absent
  local user; user=$(secret postgres-secret POSTGRES_USER)
  local exists
  exists=$("${KC[@]}" exec deploy/postgres -c postgres -- psql -U "$user" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'")
  [[ "$exists" == "1" ]] || "${KC[@]}" exec deploy/postgres -c postgres -- \
    psql -U "$user" -d postgres -qc "CREATE DATABASE ${PG_DB}"
}

seed_graph() {  # idempotent MERGE of the TCW customer graph, using any adapter venv's neo4j driver
  local py
  for py in harness/adapters/*/.venv/bin/python; do [[ -x "$py" ]] && break; done
  [[ -x "$py" ]] || die "no adapter venv found — run ./setup_venvs.sh first"
  (set -a; source .env.infra; set +a; "$py" -m scenarios.tcw.seed_neo4j)
}

up() {
  mkdir -p "$STATE"
  kubectl --context "$KUBE_CONTEXT" get deploy jaeger -n "$TRACING_NS" >/dev/null 2>&1 \
    || die "Jaeger not deployed — kubectl apply -f infrastructure/jaeger/jaeger.yaml"
  pf pf-postgres "$NS" postgres "${PG_PORT}:5432"
  pf pf-neo4j    "$NS" neo4j    "${NEO4J_PORT}:7687"
  pf pf-rabbitmq "$NS" rabbitmq "${AMQP_PORT}:5672"
  pf pf-otlp     "$TRACING_NS" jaeger-collector "${OTLP_PORT}:4318"
  pf pf-jaeger   "$TRACING_NS" tracing "${JAEGER_UI_PORT}:80"
  bg mock-api      python3 -m uvicorn scenarios.gew.mock_infrastructure.mock_api_server:app --port 8001
  bg mock-crm      python3 -m uvicorn scenarios.gew.mock_infrastructure.mock_crm_server:app --port 8002
  bg mock-approval python3 -m uvicorn scenarios.gew.mock_infrastructure.approval_server:app --port 8003
  bg mock-ml       python3 -m uvicorn scenarios.tcw.mock_infrastructure.ml_endpoint:app --port 8102
  bg mock-channel  python3 -m uvicorn scenarios.tcw.mock_infrastructure.channel_adapter:app --port 8103
  wait_port "$PG_PORT" pf-postgres; wait_port "$NEO4J_PORT" pf-neo4j; wait_port "$AMQP_PORT" pf-rabbitmq
  wait_port "$OTLP_PORT" pf-otlp; wait_port "$JAEGER_UI_PORT" pf-jaeger; for p in 8001 8002 8003 8102 8103; do wait_port "$p" "mock-$p"; done
  ensure_database
  write_env
  seed_graph
  echo "Infra up. Connection settings written to .env.infra (credentials not shown)."
}

down() {
  for f in "$STATE"/*.pid; do
    [[ -f "$f" ]] || continue
    pkill -P "$(cat "$f")" 2>/dev/null || true; kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"
  done
  echo "Infra down (cluster services untouched)."
}

status() {
  for f in "$STATE"/*.pid; do
    [[ -f "$f" ]] || continue
    kill -0 "$(cat "$f")" 2>/dev/null && s=up || s=DOWN
    printf "%-16s %s\n" "$(basename "$f" .pid)" "$s"
  done
}

case "${1:-}" in
  up) up ;; down) down ;; status) status ;;
  *) echo "usage: $0 up|down|status" >&2; exit 2 ;;
esac
