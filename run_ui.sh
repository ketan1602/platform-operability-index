#!/usr/bin/env bash
# Start the POI operator UI. Sources .env so live runs inherit AI Refinery + mock-service settings.
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
cd "$SCRIPT_DIR"

if [[ -f ".env" ]]; then set -a; source ".env"; set +a; fi
# Connection settings for the real backing services, written by ./infra.sh up.
if [[ -f ".env.infra" ]]; then set -a; source ".env.infra"; set +a; fi

PORT="${POI_UI_PORT:-8090}"

if [[ -z "${AIREFINERY_API_KEY:-}" || -z "${AIREFINERY_BASE_URL:-}" || -z "${AIREFINERY_SDK_VERSION:-}" ]]; then
  echo "warning: AI Refinery settings incomplete — live runs will be refused (dry runs still work)." >&2
fi
[[ -f ".env.infra" ]] || echo "warning: no .env.infra — run ./infra.sh up before measured scenarios." >&2

exec python3 -m uvicorn api.main:app --host 127.0.0.1 --port "$PORT"
