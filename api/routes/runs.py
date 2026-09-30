"""Launch a benchmark run and stream its progress over SSE."""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.config import FRAMEWORKS, IMPLS, MODES, REPO_ROOT, SCENARIOS, missing_live_env, results_dir

log = structlog.get_logger(__name__)
router = APIRouter()

# One run at a time: live runs share an LLM quota and the same mock services.
_run_lock = asyncio.Lock()
_COMBO_RE = re.compile(r"^\s+(OK|FAIL)\s+(.+?)\s+(GEW|TCW)\s+(fixed|idiomatic)(?::\s*(.*))?$")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _parse(csv: str, allowed: tuple[str, ...], field: str) -> list[str]:
    values = [v for v in csv.split(",") if v]
    bad = [v for v in values if v not in allowed]
    if not values or bad:
        raise HTTPException(422, f"{field}: expected subset of {allowed}, got {csv!r}")
    return values


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _line_event(line: str) -> str:
    m = _COMBO_RE.match(line)
    if not m:
        return _sse("log", {"line": line})
    status, fw_name, sc, impl, err = m.groups()
    return _sse("combo", {"ok": status == "OK", "framework": fw_name,
                          "scenario": sc, "impl": impl, "error": err})


def _child_env(mode: str, run_id: str) -> dict:
    env = {**os.environ, "POI_TRACE_ID": run_id, "PYTHONUNBUFFERED": "1"}
    env.pop("DRY_RUN", None)
    if mode == "dry_run":
        env["DRY_RUN"] = "true"
    return env


async def _stream(fws: list[str], scs: list[str], impls: list[str], mode: str):
    run_id = uuid.uuid4().hex[:12]
    total = len(fws) * len(scs) * len(impls)
    if _run_lock.locked():
        yield _sse("fatal", {"error": "A run is already in progress"})
        return
    if mode == "live" and (missing := missing_live_env()):
        yield _sse("fatal", {"error": f"Live mode needs env vars: {', '.join(missing)} (see .env.example)"})
        return
    async with _run_lock:
        out_dir = results_dir(mode)
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "harness.run_all", "--results-dir", str(out_dir),
               "--frameworks", *fws, "--scenarios", *scs, "--impls", *impls]
        log.info("run.started", run_id=run_id, mode=mode, combos=total)
        yield _sse("start", {"run_id": run_id, "total": total, "mode": mode})
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=REPO_ROOT, env=_child_env(mode, run_id),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        try:
            async for raw in proc.stdout:
                yield _line_event(_ANSI_RE.sub("", raw.decode(errors="replace").rstrip()))
            code = await proc.wait()
            log.info("run.completed", run_id=run_id, exit_code=code)
            yield _sse("done", {"run_id": run_id, "exit_code": code})
        except asyncio.CancelledError:
            log.warning("run.cancelled", run_id=run_id)
            proc.kill()
            raise


@router.get("/runs/stream")
async def stream_run(
    frameworks: str = Query(",".join(FRAMEWORKS)),
    scenarios: str = Query(",".join(SCENARIOS)),
    impls: str = Query(",".join(IMPLS)),
    mode: str = Query("live", pattern=f"^({'|'.join(MODES)})$"),
) -> StreamingResponse:
    fws = _parse(frameworks, FRAMEWORKS, "frameworks")
    scs = _parse(scenarios, SCENARIOS, "scenarios")
    ims = _parse(impls, IMPLS, "impls")
    return StreamingResponse(_stream(fws, scs, ims, mode), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
