"""Guesty task.* webhook deliveries → outcomes.

The webhook boundary (src/pms/webhooks.py) only records deliveries. This pass
reads recorded task events later and runs them through the same normalizer as
the API import. Replaying is safe: outcomes are idempotent on task id, and a
task that is not finished yet is simply skipped until a later event.
"""

from __future__ import annotations

import json
import sqlite3

from src.ops.db import ImportResult, finish_import, record_outcomes, start_import
from src.ops.sources import PropertyResolver
from src.ops.sources.guesty_tasks import normalize_task

SOURCE = "webhooks"


def import_task_webhooks(conn: sqlite3.Connection) -> ImportResult:
    result = start_import(conn, SOURCE, "outcomes")
    resolver = PropertyResolver(conn)
    rows = conn.execute(
        """SELECT event_id, event_type, payload_json FROM pms_webhook_events
           WHERE event_type LIKE 'task.%' AND event_type != 'task.deleted'
           ORDER BY received_at"""
    ).fetchall()
    latest: dict[str, dict] = {}
    for r in rows:
        payload = json.loads(r["payload_json"])
        task = payload.get("task") if isinstance(payload.get("task"), dict) else payload
        task_id = task.get("_id") or task.get("id")
        if task_id:
            latest[str(task_id)] = task  # later deliveries win
    outcomes = []
    for task in latest.values():
        try:
            o = normalize_task(task, resolver)
        except ValueError as exc:
            result.rows_in += 1
            result.rejected += 1
            result.errors.append(str(exc))
            continue
        if o is not None:
            o.source = "guesty_tasks"  # same task identity as the API import
            outcomes.append(o)
    record_outcomes(conn, outcomes, result)
    return finish_import(conn, result)
