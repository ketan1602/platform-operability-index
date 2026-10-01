#!/usr/bin/env bash
# Run the POI benchmark. Wraps run_all.py so .env and .env.infra are properly
# exported into the child-process environment (set -a exports every assignment).
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
cd "$SCRIPT_DIR"

if [[ -f ".env" ]];       then set -a; source ".env";       set +a; fi
if [[ -f ".env.infra" ]]; then set -a; source ".env.infra"; set +a; fi

: "${AIREFINERY_API_KEY:?AIREFINERY_API_KEY must be set (see .env)}"
: "${AIREFINERY_SDK_VERSION:?AIREFINERY_SDK_VERSION must be set (see .env)}"

exec python3 -m harness.run_all "$@"
