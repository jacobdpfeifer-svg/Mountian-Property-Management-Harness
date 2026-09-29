"""Vintage store: (source, key, effective_date, published_at, value)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class VintageRecord:
    source: str
    key: str
    effective_date: date
    published_at: date
    value: float | None
    vintage_id: str
    license_class: str = "publishable"
    meta: dict[str, Any] | None = None


def filter_published_at(records: Iterable[VintageRecord], as_of: date) -> list[VintageRecord]:
    return [r for r in records if r.published_at <= as_of]


class VintageStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS proving_ground_vintages (
                vintage_id TEXT NOT NULL,
                source TEXT NOT NULL,
                key TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                published_at TEXT NOT NULL,
                value REAL,
                license_class TEXT NOT NULL DEFAULT 'publishable',
                meta_json TEXT,
                PRIMARY KEY (vintage_id, source, key, effective_date)
            )
            """
        )

    def upsert(self, record: VintageRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO proving_ground_vintages (
                vintage_id, source, key, effective_date, published_at, value, license_class, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vintage_id, source, key, effective_date) DO UPDATE SET
                published_at=excluded.published_at,
                value=excluded.value,
                license_class=excluded.license_class,
                meta_json=excluded.meta_json
            """,
            (
                record.vintage_id,
                record.source,
                record.key,
                record.effective_date.isoformat(),
                record.published_at.isoformat(),
                record.value,
                record.license_class,
                json.dumps(record.meta or {}),
            ),
        )

    def read_as_of(self, source: str, as_of: date, *, key: str | None = None) -> list[VintageRecord]:
        clause = "source = ? AND published_at <= ?"
        params: list[Any] = [source, as_of.isoformat()]
        if key:
            clause += " AND key = ?"
            params.append(key)
        rows = self.conn.execute(
            f"""
            SELECT vintage_id, source, key, effective_date, published_at, value, license_class, meta_json
            FROM proving_ground_vintages
            WHERE {clause}
            ORDER BY effective_date
            """,
            params,
        ).fetchall()
        out: list[VintageRecord] = []
        for row in rows:
            out.append(VintageRecord(
                source=row["source"],
                key=row["key"],
                effective_date=date.fromisoformat(row["effective_date"]),
                published_at=date.fromisoformat(row["published_at"]),
                value=row["value"],
                vintage_id=row["vintage_id"],
                license_class=row["license_class"],
                meta=json.loads(row["meta_json"] or "{}"),
            ))
        return out

    @staticmethod
    def load_manifest(path: Path) -> list[dict[str, Any]]:
        return json.loads(path.read_text(encoding="utf-8"))
