"""Approval transport over RabbitMQ for the AHQ scenario.

Requests and decisions travel through real durable queues while the agent process
is dead. Decisions are published with at-least-once semantics — the same approval
can be delivered more than once, exactly as after a consumer crash in production.
"""
from __future__ import annotations
import json
import os
import time

import pika

REQUESTS = "poi.ahq.requests"
_EXPIRES_MS = 15 * 60 * 1000  # per-run queues clean themselves up


def _channel():
    url = os.environ.get("RABBITMQ_URL", "")
    if not url:
        raise RuntimeError("RABBITMQ_URL must be set (run ./infra.sh up)")
    params = pika.URLParameters(url)
    # Tolerate brief broker unavailability (e.g. a restarting port-forward in local dev).
    params.connection_attempts, params.retry_delay = 10, 1
    conn = pika.BlockingConnection(params)
    return conn, conn.channel()


def _decision_queue(ch, run_id: str) -> str:
    name = f"poi.ahq.decision.{run_id}"
    ch.queue_declare(name, durable=True, arguments={"x-expires": _EXPIRES_MS})
    return name


def publish_request(run_id: str, action: dict) -> None:
    conn, ch = _channel()
    ch.queue_declare(REQUESTS, durable=True)
    body = json.dumps({"run_id": run_id, "action": action})
    ch.basic_publish("", REQUESTS, body, pika.BasicProperties(delivery_mode=2))
    conn.close()


def publish_decision(run_id: str, approved: bool, copies: int = 1) -> None:
    conn, ch = _channel()
    q = _decision_queue(ch, run_id)
    for _ in range(copies):
        ch.basic_publish("", q, json.dumps({"approved": approved}), pika.BasicProperties(delivery_mode=2))
    conn.close()


def wait_decision(run_id: str, timeout_s: float = 120.0) -> dict:
    conn, ch = _channel()
    q = _decision_queue(ch, run_id)
    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline:
            method, _, body = ch.basic_get(q, auto_ack=True)
            if method:
                return json.loads(body)
            time.sleep(0.5)
    finally:
        conn.close()
    raise TimeoutError(f"no approval decision for {run_id} within {timeout_s}s")
