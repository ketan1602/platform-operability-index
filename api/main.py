"""POI benchmark operator UI — FastAPI app serving the API and static frontend."""
from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes import health, results, runs

app = FastAPI(title="Platform Operability Index")
app.include_router(health.router)
app.include_router(results.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
