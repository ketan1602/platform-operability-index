#!/usr/bin/env bash
# Run the POI benchmark. Wraps run_all.py so .env and .env.infra are properly
# exported into the child-process environment (set -a exports every assignment).
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
cd "$SCRIPT_DIR"

if [[ -f ".env" ]];       then set -a; source ".env";       set +a; fi
if [[ -f ".env.infra" ]]; then set -a; source ".env.infra"; set +a; fi

# Accept either the generic names (preferred) or the legacy AIREFINERY_* alias names.
_api_key="${LLM_API_KEY:-${AIREFINERY_API_KEY:-}}"
_base_url="${LLM_BASE_URL:-${AIREFINERY_BASE_URL:-}}"

if [[ -z "$_api_key" ]]; then
  echo "ERROR: LLM_API_KEY must be set (see .env.example for OpenAI, Anthropic, and self-hosted endpoint examples)" >&2
  exit 1
fi
if [[ -z "$_base_url" ]]; then
  echo "ERROR: LLM_BASE_URL must be set (e.g. https://api.openai.com/v1)" >&2
  exit 1
fi

exec python3 -m harness.run_all "$@"
