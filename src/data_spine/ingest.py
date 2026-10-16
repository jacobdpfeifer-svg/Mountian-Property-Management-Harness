"""Append-only ingestion into the data spine.

`ingest` validates each record against its contract and then, in one
transaction, either:

- skips it as a duplicate (same source system and content hash),
- appends version 1 of a new entity,
- appends version N+1 that supersedes the current version (a correction or a
  source update), or
- quarantines it with reason codes.

A source update that is older than the version already held is quarantined as
`OUT_OF_ORDER_VERSION` rather than allowed to overwrite newer truth.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from src.data_spine.contracts import CONTRACTS, LEDGER_ENTRY_DIRECTION, Contract, Reason, validate

# Contract field that becomes entity_key in each table.
_KEY_FIELD = {
    "price_decision": "decision_key",
    "reservation": "reservation_key",
    "financial_ledger": "entry_key",
    "owner_statement": "statement_key",
    "ops_task": "task_key",
    "listing_constraint": "constraint_key",
}


@dataclass
class IngestResult:
    batch_id: str
    contract: str
    accepted: list[int] = field(default_factory=list)       # new fact row ids
    duplicates: int = 0
    quarantined: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.quarantined


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def content_hash(clean: dict[str, Any]) -> str:
    """sha256 of the contract payload, excluding when we happened to observe it."""
    body = {k: v for k, v in clean.items() if k != "observed_at"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _row_values(contract: Contract, clean: dict[str, Any]) -> dict[str, Any]:
    key_field = _KEY_FIELD.get(contract.name)
    values = {k: v for k, v in clean.items() if k != key_field and k != "correction_reason"}
    if contract.name == "financial_ledger" and not values.get("direction"):
        values["direction"] = LEDGER_ENTRY_DIRECTION[clean["entry_type"]]
    return values


def _quarantine(conn: sqlite3.Connection, result: IngestResult, contract: Contract,
                clean: dict[str, Any], problems: list[tuple[str, str]], entity_key: str | None) -> None:
    codes = sorted({code for code, _ in problems})
    detail = "; ".join(f"{code}:{name}" for code, name in problems)
    conn.execute(
        """INSERT INTO spine_quarantine (batch_id, contract_name, entity_key, reason_codes,
               detail, payload_json, source_hash, quarantined_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (result.batch_id, contract.name, entity_key, json.dumps(codes), detail,
         json.dumps(clean, sort_keys=True, default=str), content_hash(clean), _now()),
    )
    result.quarantined.append({"entity_key": entity_key, "reasons": codes, "detail": detail})


def _insert_nights(conn: sqlite3.Connection, version_id: int, clean: dict[str, Any]) -> None:
    if clean["status"] == "cancelled":
        return
    nights = int(clean["nights"])
    per_night = round(float(clean["gross_lodging"]) / nights, 2)
    start = date.fromisoformat(clean["check_in"])
    for i in range(nights):
        conn.execute(
            """INSERT INTO fact_reservation_night
                   (reservation_version_id, property_id, stay_date, nightly_lodging, price_basis)
               VALUES (?, ?, ?, ?, 'nightly_ex_fees')""",
            (version_id, clean["property_id"], (start + timedelta(days=i)).isoformat(), per_night),
        )


def ingest(
    conn: sqlite3.Connection,
    contract_name: str,
    records: Iterable[dict[str, Any]],
    *,
    allowed_property_ids: frozenset[str],
    batch_id: str | None = None,
) -> IngestResult:
    """Validate and append `records`. One transaction; all-or-nothing on SQL error."""
    contract = CONTRACTS[contract_name]
    records = list(records)
    result = IngestResult(batch_id or uuid.uuid4().hex, contract.name)
    source_systems = {str(r.get("source_system") or "unknown") for r in records} or {"unknown"}
    if conn.in_transaction:
        # Never commit a caller's transaction behind its back.  That could make
        # a partially assembled ingest visible before the caller has completed
        # its own validation.  Callers need a fresh connection/transaction.
        raise RuntimeError("data-spine ingest requires no active transaction")
    with conn:
        # The batch row is written last, once its counts are known, so foreign
        # keys to it are checked at COMMIT. The pragma resets after each commit.
        conn.execute("BEGIN")
        conn.execute("PRAGMA defer_foreign_keys = ON")
        for raw in records:
            clean, problems = validate(contract, raw, allowed_property_ids)
            entity_key = contract.key(clean) if not any(
                c == Reason.MISSING_FIELD for c, _ in problems) else None
            if problems:
                _quarantine(conn, result, contract, clean, problems, entity_key)
                continue
            assert entity_key is not None
            digest = content_hash(clean)
            if conn.execute(
                f"SELECT 1 FROM {contract.table} WHERE source_system=? AND source_hash=?",
                (clean["source_system"], digest),
            ).fetchone():
                result.duplicates += 1
                continue
            latest = conn.execute(
                f"""SELECT id, version_no, source_updated_at FROM {contract.table}
                    WHERE entity_key=? ORDER BY version_no DESC LIMIT 1""",
                (entity_key,),
            ).fetchone()
            if latest is not None and _ts(clean["source_updated_at"]) < _ts(latest["source_updated_at"]):
                _quarantine(conn, result, contract, clean,
                            [(Reason.OUT_OF_ORDER_VERSION, "source_updated_at")], entity_key)
                continue
            values = _row_values(contract, clean)
            values.update({
                "entity_key": entity_key,
                "version_no": 1 if latest is None else int(latest["version_no"]) + 1,
                "supersedes_id": None if latest is None else int(latest["id"]),
                "correction_reason": None if latest is None else (clean.get("correction_reason") or "source_update"),
                "source_hash": digest,
                "schema_version": contract.schema_version,
                "ingested_at": _now(),
                "batch_id": result.batch_id,
            })
            cols = sorted(values)
            cur = conn.execute(
                f"INSERT INTO {contract.table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [values[c] for c in cols],
            )
            row_id = int(cur.lastrowid or 0)
            if contract.name == "reservation":
                _insert_nights(conn, row_id, clean)
            result.accepted.append(row_id)
        conn.execute(
            """INSERT INTO spine_source_batch (batch_id, contract_name, schema_version, source_system,
                   received_at, record_count, accepted, duplicates, quarantined)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result.batch_id, contract.name, contract.schema_version, ",".join(sorted(source_systems)),
             _now(), len(records), len(result.accepted), result.duplicates, len(result.quarantined)),
        )
    return result


def current_rows(conn: sqlite3.Connection, table: str, where: str = "1=1",
                 params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    """Rows of `table` that no later version supersedes."""
    return conn.execute(
        f"""SELECT * FROM {table} t
            WHERE {where}
              AND NOT EXISTS (SELECT 1 FROM {table} s WHERE s.supersedes_id = t.id)
            ORDER BY t.entity_key, t.version_no""",
        params,
    ).fetchall()
