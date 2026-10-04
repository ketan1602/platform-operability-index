# Contributing to the POI Benchmark

## Quick start

```bash
git clone https://github.com/ketan1602/platform-operability-index
cd platform-operability-index
./setup_venvs.sh
cp .env.example .env   # set LLM_BASE_URL + LLM_API_KEY + MODEL_ID

# Validate everything works — no LLM, no infra needed
DRY_RUN=true python3 -m harness.run_all --scenarios GEW TCW

# Run tests
python3 -m pytest tests/ -v
```

## Adding a new framework

1. Create `harness/adapters/{fw_name}/` and copy the structure of an existing adapter (e.g. `langgraph`).
2. Implement the pillar measurement functions: `p1_measure.py`, `p2_measure.py`, ..., `p9_measure.py`.
3. Implement the scenario workflows under `scenarios/*/implementations/{fw_name}/`.
4. Add the venv install to `setup_venvs.sh` (one `uv venv` + `uv pip install` block).
5. Register the framework ID in `harness/run_all.py` and `harness/adapters/base.py`.
6. Run `DRY_RUN=true python3 -m harness.run_all --frameworks {fw_name}` to validate dry-run.

## Adding a new scenario

1. Create `scenarios/{name}/` with `__init__.py` and a `measure.py` that returns the appropriate `P*Measurements` model.
2. Register the scenario in `harness/adapters/base.py`'s `MEASURED` dict.
3. Add a dry-run fixture for `DRY_RUN=true` to `harness/shared/dry_run_fixtures.py`.

## Code style

- 150-line file limit (excluding blanks and comments). Split before you reach it.
- `structlog` for all logging — no `print()`.
- No hardcoded secrets, URLs, or service addresses. Read from env vars only.
- Run `python3 -m pytest tests/ -v` and fix all failures before opening a PR.
- Run `python3 -m ruff check .` and fix all lint errors.

## Pillar model changes

Changes to `harness/shared/pillar_models.py` affect all five framework adapters. Always update all affected adapter `p*_measure.py` files in the same PR and verify with a dry-run across all frameworks.

## Reporting issues

Open a GitHub issue with:
- Which framework and scenario failed
- The exact command you ran
- The full error output
- Your `LLM_BASE_URL` provider (no keys — just the host, e.g. `api.openai.com`)
- Output of `python3 --version` and `uv --version`
