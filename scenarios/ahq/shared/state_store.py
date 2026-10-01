"""Postgres persistence for frameworks that serialise state but have no durable store.

Frameworks with a native durable backend never import this. Every line is counted
as operability tax for the frameworks that do (see harness.shared.custom_loc).
"""
from __future__ import annotations
import os

import psycopg

# poi:custom-begin
_DDL = "CREATE TABLE IF NOT EXISTS poi_ahq_state (run_id TEXT PRIMARY KEY, state TEXT NOT NULL)"


def _connect():
    return psycopg.connect(os.environ["POSTGRES_URL"], autocommit=True)


def save(run_id: str, state: str) -> None:
    with _connect() as conn:
        conn.execute(_DDL)
        conn.execute(
            "INSERT INTO poi_ahq_state (run_id, state) VALUES (%s, %s) "
            "ON CONFLICT (run_id) DO UPDATE SET state = EXCLUDED.state",
            (run_id, state),
        )


def load(run_id: str) -> str:
    with _connect() as conn:
        row = conn.execute("SELECT state FROM poi_ahq_state WHERE run_id = %s", (run_id,)).fetchone()
    if row is None:
        raise LookupError(f"no persisted state for run {run_id}")
    return row[0]
# poi:custom-end
