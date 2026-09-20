"""Checkpointer factory for GEW LangGraph fixed implementation.

OT-LOC: Every non-blank, non-comment line in this file counts as
platform-glue cost because LangGraph does not auto-read CHECKPOINT_BACKEND_URL.
"""
from __future__ import annotations
import os
import structlog

log = structlog.get_logger(__name__)


def build_checkpointer():
    """Return a checkpointer driven by CHECKPOINT_BACKEND_URL.

    Falls back to MemorySaver when the env var is absent or psycopg
    is not installed.
    """
    from langgraph.checkpoint.memory import MemorySaver

    url = os.environ.get("CHECKPOINT_BACKEND_URL", "")
    if not url:
        return MemorySaver()

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        import psycopg  # noqa: F401
        conn = psycopg.connect(url)
        saver = PostgresSaver(conn)
        saver.setup()
        log.info("checkpointer.postgres_connected", url=url[:40])
        return saver
    except ImportError:
        log.warning(
            "checkpointer.psycopg_unavailable",
            fallback="MemorySaver",
            hint="pip install psycopg[binary]",
        )
        return MemorySaver()
