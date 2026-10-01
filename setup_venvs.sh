#!/usr/bin/env bash
# Create one Python 3.12 venv per framework adapter (frameworks' deps conflict if shared).
set -euo pipefail
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"; [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]] && SCRIPT_DIR="."
cd "$SCRIPT_DIR"
PY="${POI_VENV_PYTHON:-3.12}"
for dir in harness/adapters/{langgraph,ms_agent,openai_sdk,google_adk,strands}; do
  echo "==> $dir"
  uv venv --quiet --allow-existing --python "$PY" "$dir/.venv"
  (cd "$dir" && uv pip install --quiet --python .venv/bin/python -r requirements.txt)
done
echo "All adapter venvs ready."
