"""Column-mapped CSV import for every operations table.

Kinds: outcomes, capacity, asset_events, ledger, credentials.

Presets map vendor export headers to canonical fields. Vendor presets
(turno, breezeway_export, guesty_tasks_export) are best-effort mappings from
public help-center screenshots and have NOT been checked against a real export.
Unknown headers are ignored; a row missing a required field is rejected and
reported, never guessed. Templates live in data/sample/ops/.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

from src.ops import AssetEvent, CapacitySnapshot, TurnoverOutcome
from src.ops.db import (
    ImportResult,
    finish_import,
    record_asset_event,
    record_capacity,
    record_outcomes,
    start_import,
)
from src.ops.sources import PropertyResolver
from src.ops.sources.normalize import (
    CANCELLED,
    as_bool,
    as_float,
    as_iso_date,
    as_iso_datetime,
    as_minutes,
    blank,
    minutes_between,
    service_type_for,
)

KINDS = ("outcomes", "capacity", "asset_events", "ledger", "credentials")

# canonical field -> accepted headers (normalized: lower, single spaces)
OUTCOME_PRESETS: dict[str, dict[str, list[str]]] = {
    "generic": {
        "property": ["property_id", "property"],
        "task_id": ["source_task_id", "task_id"],
        "service_date": ["service_date", "date"],
        "service_type": ["service_type", "type"],
        "turn_id": ["turn_id"],
        "scheduled_start": ["scheduled_start"],
        "started_at": ["started_at"],
        "completed_at": ["completed_at"],
        "required_minutes": ["required_minutes"],
        "actual_minutes": ["actual_minutes"],
        "cost": ["cost"],
        "qa_pass": ["qa_pass"],
        "rework_minutes": ["rework_minutes"],
        "late_ready_minutes": ["late_ready_minutes"],
        "assignee": ["assignee_ref", "assignee"],
        "status": ["status"],
    },
    "turno": {
        "property": ["property", "property name", "property address", "address"],
        "task_id": ["project id", "project", "job id", "id"],
        "service_date": ["date", "project date", "cleaning date"],
        "service_type": ["service", "project type", "type"],
        "scheduled_start": ["start time", "scheduled start"],
        "started_at": ["started at", "check in time", "cleaner check in"],
        "completed_at": ["completed at", "finished at", "completion time", "cleaner check out"],
        "actual_minutes": ["duration", "duration (minutes)", "time spent"],
        "cost": ["price", "total", "total price", "amount", "cost"],
        "qa_pass": ["approved", "qa"],
        "assignee": ["cleaner", "cleaner name", "assigned to"],
        "status": ["status", "project status"],
    },
    "breezeway_export": {
        "property": ["property reference id", "property reference", "property name", "property"],
        "task_id": ["task id", "id"],
        "service_date": ["scheduled date", "due date", "date"],
        "service_type": ["department", "type", "task type", "template"],
        "scheduled_start": ["scheduled time", "scheduled start"],
        "started_at": ["started at", "start time", "started"],
        "completed_at": ["finished at", "completed at", "finished", "completed"],
        "actual_minutes": ["total time", "time spent", "duration"],
        "cost": ["total cost", "cost", "labor cost"],
        "qa_pass": ["inspection passed", "passed"],
        "assignee": ["assignee", "assigned to", "assignees"],
        "status": ["status", "task status"],
    },
    "guesty_tasks_export": {
        "property": ["listing id", "listing", "listing nickname", "listing title"],
        "task_id": ["task id", "id", "_id"],
        "service_date": ["start date", "due date", "date", "scheduled for"],
        "service_type": ["task type", "type", "title"],
        "scheduled_start": ["start time", "start date"],
        # Guesty tasks have no separate start stamp; duration runs from the
        # task start, as in the API normalizer (src/ops/sources/guesty_tasks.py).
        "started_at": ["started at", "start time", "start date"],
        "completed_at": ["completion date", "completed at", "done at"],
        "actual_minutes": ["duration", "actual duration"],
        "cost": ["cost", "price", "task cost"],
        "assignee": ["assignee", "assigned to"],
        "status": ["status"],
    },
}
PRESETS = tuple(OUTCOME_PRESETS)


def _norm(header: str) -> str:
    return re.sub(r"[\s_]+", " ", str(header or "").strip().lower())


def _getter(headers: list[str], mapping: dict[str, list[str]]) -> Callable[[dict[str, str], str], Any]:
    normalized = {_norm(h): h for h in headers}
    resolved: dict[str, str] = {}
    for field, candidates in mapping.items():
        for cand in candidates:
            if _norm(cand) in normalized:
                resolved[field] = normalized[_norm(cand)]
                break

    def get(row: dict[str, str], field: str) -> Any:
        col = resolved.get(field)
        return None if col is None else row.get(col)

    return get


def _row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]


def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def parse_outcomes(
    headers: list[str],
    rows: list[dict[str, str]],
    *,
    preset: str,
    source: str,
    resolver: PropertyResolver,
) -> tuple[list[TurnoverOutcome], list[str]]:
    if preset not in OUTCOME_PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose from {PRESETS}")
    get = _getter(headers, OUTCOME_PRESETS[preset])
    out: list[TurnoverOutcome] = []
    errors: list[str] = []
    for i, row in enumerate(rows, start=2):
        status = str(get(row, "status") or "").strip().lower()
        if status in CANCELLED:
            continue
        pid = resolver.resolve(get(row, "property"))
        if pid is None:
            errors.append(f"line {i}: unknown property {get(row, 'property')!r}")
            continue
        service_date = as_iso_date(get(row, "service_date")) or as_iso_date(get(row, "completed_at"))
        task_id = get(row, "task_id")
        if blank(task_id):
            task_id = f"row_{_row_hash(row)}"
        actual = as_minutes(get(row, "actual_minutes"))
        if actual is None:
            actual = minutes_between(get(row, "started_at"), get(row, "completed_at"))
        qa = as_bool(get(row, "qa_pass"))
        out.append(TurnoverOutcome(
            property_id=pid,
            service_date=service_date or "",
            source=source,
            source_task_id=str(task_id).strip(),
            service_type=service_type_for(get(row, "service_type")),
            turn_id=(str(get(row, "turn_id")).strip() or None) if not blank(get(row, "turn_id")) else None,
            scheduled_start=as_iso_datetime(get(row, "scheduled_start")),
            completed_at=as_iso_datetime(get(row, "completed_at")),
            required_minutes=as_minutes(get(row, "required_minutes")),
            actual_minutes=actual,
            cost=as_float(get(row, "cost")),
            qa_pass=qa,
            rework_minutes=as_minutes(get(row, "rework_minutes")),
            late_ready_minutes=as_float(get(row, "late_ready_minutes")),
            assignee_ref=None if blank(get(row, "assignee")) else str(get(row, "assignee")).strip(),
            raw={"preset": preset, "line": i},
        ))
    return out, errors


def _import_outcomes(conn, headers, rows, preset, source, resolver, result):
    outcomes, errors = parse_outcomes(headers, rows, preset=preset, source=source, resolver=resolver)
    result.errors.extend(errors)
    result.rows_in += len(errors)
    result.rejected += len(errors)
    return record_outcomes(conn, outcomes, result)


def _import_capacity(conn, headers, rows, source, result):
    snaps = []
    for i, row in enumerate(rows, start=2):
        avail = as_float(row.get("available_worker_minutes"))
        date_s = as_iso_date(row.get("service_date"))
        if avail is None or date_s is None or blank(row.get("access_zone")):
            result.rows_in += 1
            result.rejected += 1
            result.errors.append(f"line {i}: needs service_date, access_zone, available_worker_minutes")
            continue
        snaps.append(CapacitySnapshot(
            as_of=as_iso_date(row.get("as_of")) or date_s,
            service_date=date_s,
            access_zone=str(row["access_zone"]).strip(),
            available_worker_minutes=avail,
            committed_worker_minutes=as_float(row.get("committed_worker_minutes")) or 0.0,
            service_type=str(row.get("service_type") or "turnover").strip() or "turnover",
            source=source,
            confidence=as_float(row.get("confidence")) if not blank(row.get("confidence")) else 0.7,
        ))
    return record_capacity(conn, snaps, result)


def _import_asset_events(conn, headers, rows, resolver, result):
    reading_cols = [h for h in headers if h.startswith("reading_")]
    for i, row in enumerate(rows, start=2):
        result.rows_in += 1
        pid = resolver.resolve(row.get("property_id"), row.get("property"))
        observed = as_iso_datetime(row.get("observed_at"))
        if pid is None or observed is None or blank(row.get("system_type")):
            result.rejected += 1
            result.errors.append(f"line {i}: needs known property, observed_at, system_type")
            continue
        reading: dict[str, Any] = {}
        if not blank(row.get("reading_json")):
            reading.update(json.loads(row["reading_json"]))
        for col in reading_cols:
            if col != "reading_json" and not blank(row.get(col)):
                val = as_float(row[col])
                reading[col.removeprefix("reading_")] = val if val is not None else row[col]
        try:
            _, created = record_asset_event(conn, AssetEvent(
                property_id=pid,
                system_type=str(row["system_type"]).strip(),
                observed_at=observed,
                severity=str(row.get("severity") or "warn").strip(),
                source_type=str(row.get("source_type") or "manual").strip(),
                effective_from=as_iso_date(row.get("effective_from")),
                effective_to=as_iso_date(row.get("effective_to")),
                source_ref=None if blank(row.get("source_ref")) else str(row["source_ref"]),
                reading=reading,
                verified_by=None if blank(row.get("verified_by")) else str(row["verified_by"]),
            ))
        except sqlite3.IntegrityError as exc:
            result.rejected += 1
            result.errors.append(f"line {i}: {exc}")
            continue
        if created:
            result.accepted += 1
        else:
            result.duplicates += 1
    return result


def _import_ledger(conn, rows, resolver, source, result):
    from src.db import PROPERTY_OWNER_IDS

    for i, row in enumerate(rows, start=2):
        result.rows_in += 1
        pid = resolver.resolve(row.get("property_id"), row.get("property"))
        owner = (row.get("owner_id") or "").strip() or (PROPERTY_OWNER_IDS.get(pid or "") or "")
        amount = as_float(row.get("amount"))
        entry_date = as_iso_date(row.get("entry_date") or row.get("date"))
        category = str(row.get("category") or "").strip().lower()
        if not owner or amount is None or entry_date is None or not category:
            result.rejected += 1
            result.errors.append(f"line {i}: needs owner/property, entry_date, category, amount")
            continue
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO owner_ledger_entries
                   (owner_id, property_id, entry_date, category, amount, memo, source, evidence_ref)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (owner, pid, entry_date, category, amount, (row.get("memo") or "").strip(),
                 source, (row.get("evidence_ref") or "").strip() or None),
            )
        except sqlite3.IntegrityError as exc:
            result.rejected += 1
            result.errors.append(f"line {i}: {exc}")
            continue
        if cur.rowcount:
            result.accepted += 1
        else:
            result.duplicates += 1
    return result


def _import_credentials(conn, rows, resolver, result):
    from src.compliance import Credential, add_credential

    for i, row in enumerate(rows, start=2):
        result.rows_in += 1
        pid = resolver.resolve(row.get("property_id"), row.get("property"))
        if pid is None or blank(row.get("credential_type")) or blank(row.get("jurisdiction")):
            result.rejected += 1
            result.errors.append(f"line {i}: needs known property, jurisdiction, credential_type")
            continue
        created = add_credential(conn, Credential(
            property_id=pid,
            jurisdiction=str(row["jurisdiction"]).strip(),
            credential_type=str(row["credential_type"]).strip(),
            identifier=None if blank(row.get("identifier")) else str(row["identifier"]).strip(),
            issued_at=as_iso_date(row.get("issued_at")),
            expires_at=as_iso_date(row.get("expires_at")),
            evidence_ref=None if blank(row.get("evidence_ref")) else str(row["evidence_ref"]).strip(),
            verification_status=str(row.get("verification_status") or "unverified").strip(),
            verified_by=None if blank(row.get("verified_by")) else str(row["verified_by"]).strip(),
            notes=None if blank(row.get("notes")) else str(row["notes"]),
        ))
        if created:
            result.accepted += 1
        else:
            result.duplicates += 1
    return result


def import_csv(
    conn: sqlite3.Connection,
    path: Path | str,
    *,
    kind: str = "outcomes",
    preset: str = "generic",
    source: str | None = None,
) -> ImportResult:
    """Import one CSV. `source` defaults to csv:<preset> for outcomes, csv otherwise."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; choose from {KINDS}")
    path = Path(path)
    headers, rows = _read(path)
    src = source or (f"csv:{preset}" if kind == "outcomes" else "csv")
    result = start_import(conn, "csv", kind)
    resolver = PropertyResolver(conn)
    try:
        if kind == "outcomes":
            _import_outcomes(conn, headers, rows, preset, src, resolver, result)
        elif kind == "capacity":
            _import_capacity(conn, headers, rows, src, result)
        elif kind == "asset_events":
            _import_asset_events(conn, headers, rows, resolver, result)
        elif kind == "ledger":
            _import_ledger(conn, rows, resolver, src, result)
        else:
            _import_credentials(conn, rows, resolver, result)
    except Exception as exc:  # recorded, then re-raised for the CLI
        result.errors.append(f"{type(exc).__name__}: {exc}")
        finish_import(conn, result, status="failed")
        raise
    return finish_import(conn, result)
