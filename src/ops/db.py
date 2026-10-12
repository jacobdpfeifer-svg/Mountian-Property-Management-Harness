"""Operations tables and the single write path every source goes through."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from src.ops import AssetEvent, CapacitySnapshot, TurnoverOutcome

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def ensure_ops_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


@dataclass
class ImportResult:
    run_id: str
    source: str
    kind: str
    rows_in: int = 0
    accepted: int = 0
    duplicates: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "ok"

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id, "source": self.source, "kind": self.kind,
            "rows_in": self.rows_in, "accepted": self.accepted,
            "duplicates": self.duplicates, "rejected": self.rejected,
            "status": self.status, "errors": self.errors[:10],
        }


def start_import(conn: sqlite3.Connection, source: str, kind: str) -> ImportResult:
    ensure_ops_tables(conn)
    run_id = f"ops_{source}_{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT INTO ops_import_runs (run_id, source, kind) VALUES (?, ?, ?)",
        (run_id, source, kind),
    )
    return ImportResult(run_id=run_id, source=source, kind=kind)


def finish_import(conn: sqlite3.Connection, result: ImportResult, status: str | None = None) -> ImportResult:
    if status:
        result.status = status
    elif result.rejected and result.accepted + result.duplicates:
        result.status = "partial"
    elif result.rejected:
        result.status = "failed"
    conn.execute(
        """UPDATE ops_import_runs SET finished_at=datetime('now'), status=?, rows_in=?,
               accepted=?, rejected=?, errors=? WHERE run_id=?""",
        (result.status, result.rows_in, result.accepted, result.rejected,
         json.dumps(result.errors[:50]), result.run_id),
    )
    conn.commit()
    return result


def _bool_or_none(value: bool | None) -> int | None:
    return None if value is None else int(bool(value))


def record_outcomes(
    conn: sqlite3.Connection, outcomes: Iterable[TurnoverOutcome], result: ImportResult
) -> ImportResult:
    """Idempotent on (source, source_task_id). A re-import refreshes the row."""
    for o in outcomes:
        result.rows_in += 1
        if not o.property_id or not o.service_date or not o.source_task_id:
            result.rejected += 1
            result.errors.append(f"missing property/date/task id: {o.source_task_id!r}")
            continue
        existed = conn.execute(
            "SELECT 1 FROM turnover_outcomes WHERE source=? AND source_task_id=?",
            (o.source, o.source_task_id),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO turnover_outcomes (
                turn_id, property_id, service_date, service_type, scheduled_start,
                completed_at, required_minutes, actual_minutes, cost, qa_pass,
                rework_minutes, late_ready_minutes, assignee_ref, source, source_task_id,
                import_run_id, raw_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source, source_task_id) DO UPDATE SET
                turn_id=COALESCE(excluded.turn_id, turnover_outcomes.turn_id),
                property_id=excluded.property_id,
                service_date=excluded.service_date,
                service_type=excluded.service_type,
                scheduled_start=excluded.scheduled_start,
                completed_at=excluded.completed_at,
                required_minutes=excluded.required_minutes,
                actual_minutes=excluded.actual_minutes,
                cost=excluded.cost,
                qa_pass=excluded.qa_pass,
                rework_minutes=excluded.rework_minutes,
                late_ready_minutes=excluded.late_ready_minutes,
                assignee_ref=excluded.assignee_ref,
                import_run_id=excluded.import_run_id,
                raw_json=excluded.raw_json,
                imported_at=datetime('now')
            """,
            (
                o.turn_id, o.property_id, o.service_date, o.service_type, o.scheduled_start,
                o.completed_at, o.required_minutes, o.actual_minutes, o.cost,
                _bool_or_none(o.qa_pass), o.rework_minutes, o.late_ready_minutes,
                o.assignee_ref, o.source, o.source_task_id, result.run_id,
                json.dumps(o.raw, sort_keys=True, default=str) if o.raw else None,
            ),
        )
        if existed:
            result.duplicates += 1
        else:
            result.accepted += 1
    return result


def record_capacity(
    conn: sqlite3.Connection, snapshots: Iterable[CapacitySnapshot], result: ImportResult
) -> ImportResult:
    for s in snapshots:
        result.rows_in += 1
        if s.available_worker_minutes < 0 or s.committed_worker_minutes < 0:
            result.rejected += 1
            result.errors.append(f"negative minutes for {s.service_date} {s.access_zone}")
            continue
        existed = conn.execute(
            """SELECT 1 FROM operations_capacity_snapshots WHERE as_of=? AND service_date=?
               AND access_zone=? AND service_type=? AND source=?""",
            (s.as_of, s.service_date, s.access_zone, s.service_type, s.source),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO operations_capacity_snapshots (
                as_of, service_date, access_zone, service_type, available_worker_minutes,
                committed_worker_minutes, source, confidence, import_run_id
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(as_of, service_date, access_zone, service_type, source) DO UPDATE SET
                available_worker_minutes=excluded.available_worker_minutes,
                committed_worker_minutes=excluded.committed_worker_minutes,
                confidence=excluded.confidence,
                import_run_id=excluded.import_run_id
            """,
            (s.as_of, s.service_date, s.access_zone, s.service_type,
             float(s.available_worker_minutes), float(s.committed_worker_minutes),
             s.source, float(s.confidence), result.run_id),
        )
        if existed:
            result.duplicates += 1
        else:
            result.accepted += 1
    return result


def asset_event_id(e: AssetEvent) -> str:
    raw = "|".join([
        e.property_id, e.system_type, e.observed_at, e.source_type, e.source_ref or "",
        json.dumps(e.reading, sort_keys=True, default=str),
    ])
    return "evt_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def record_asset_event(conn: sqlite3.Connection, e: AssetEvent) -> tuple[str, bool]:
    """Insert one asset-health event. Returns (event_id, created)."""
    ensure_ops_tables(conn)
    event_id = e.event_id or asset_event_id(e)
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO asset_health_events (
            event_id, property_id, system_type, observed_at, effective_from, effective_to,
            severity, source_type, source_ref, reading_json, verified_by
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (event_id, e.property_id, e.system_type, e.observed_at,
         e.effective_from or e.observed_at[:10], e.effective_to, e.severity, e.source_type,
         e.source_ref, json.dumps(e.reading, sort_keys=True, default=str), e.verified_by),
    )
    return event_id, cur.rowcount > 0
