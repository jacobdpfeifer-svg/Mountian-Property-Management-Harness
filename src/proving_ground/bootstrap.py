"""Disposable DB bootstrap for Proving Ground engine runs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.db import DB_KIND_DEMO, connect, init_db, mark_db_identity
from src.ingest import CsvIngestAdapter

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample"


def bootstrap_disposable_db(db_path: Path, *, property_id: str = "cabin_ridge") -> sqlite3.Connection:
    """Create a demo DB seeded from ``data/sample/`` for one property."""
    init_db(db_path)
    conn = connect(db_path)
    adapter = CsvIngestAdapter(
        properties_csv=SAMPLE / "properties.csv",
        inventory_csv=SAMPLE / "nightly_inventory.csv",
        comps_csv=SAMPLE / "comps.csv",
        demand_csv=SAMPLE / "demand_signals.csv",
    )
    adapter.load_all(conn)
    mark_db_identity(conn, DB_KIND_DEMO, "proving_ground", force=True)
    conn.execute(
        "UPDATE properties SET market_id = 'grand_home' WHERE property_id = ?",
        (property_id,),
    )
    conn.commit()
    return conn
