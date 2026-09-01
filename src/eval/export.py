"""Export recommendations and inventory to CSV."""

from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path


def export_recommendations_csv(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    path: Path | str,
    property_ids: list[str] | None = None,
) -> int:
    sql = """
        SELECT property_id, stay_date, listed_price_at_run, recommended_price,
               expected_book_prob, expected_revpan, ceiling_price, ceiling_confidence,
               floor_price, autonomy_level, guardrail_action, status, run_id
        FROM price_recommendations
        WHERE stay_date >= ? AND stay_date <= ?
    """
    params: list[object] = [start.isoformat(), end.isoformat()]
    if property_ids:
        placeholders = ",".join("?" for _ in property_ids)
        sql += f" AND property_id IN ({placeholders})"
        params.extend(property_ids)
    sql += " ORDER BY property_id, stay_date"

    rows = conn.execute(sql, params).fetchall()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "property_id", "stay_date", "listed_price_at_run", "recommended_price",
        "expected_book_prob", "expected_revpan", "ceiling_price", "ceiling_confidence",
        "floor_price", "autonomy_level", "guardrail_action", "status", "run_id",
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in fields})
    return len(rows)
