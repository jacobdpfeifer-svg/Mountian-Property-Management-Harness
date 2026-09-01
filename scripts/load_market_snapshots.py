#!/usr/bin/env python3
"""Load market_snapshots from data/dec2023/market_snapshots.csv into the DB."""
from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db import connect, init_db


def load_market_snapshots(db_path: str, csv_path: str) -> int:
    init_db(db_path)
    path = Path(csv_path)
    n = 0
    with connect(db_path) as conn:
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    """
                    INSERT INTO market_snapshots (
                        as_of, stay_date, window_nights, region,
                        listings, p25, p50, p75, p90, run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(as_of, stay_date, region) DO UPDATE SET
                        listings=excluded.listings, p25=excluded.p25,
                        p50=excluded.p50, p75=excluded.p75, p90=excluded.p90,
                        run_id=excluded.run_id
                    """,
                    (
                        row["as_of"],
                        row["stay_date"],
                        int(row["window_nights"]),
                        row["region"],
                        int(row["listings"]),
                        float(row["p25"]),
                        float(row["p50"]),
                        float(row["p75"]),
                        float(row["p90"]),
                        row["run_id"],
                    ),
                )
                n += 1
        conn.commit()
    return n


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "data/dec2023_run.db"
    csv_file = sys.argv[2] if len(sys.argv) > 2 else "data/dec2023/market_snapshots.csv"
    count = load_market_snapshots(db, csv_file)
    print(f"Loaded {count} market snapshots into {db}")
