"""Database helpers (SQLite by default)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wp_pricing.db"

# Columns added after initial CREATE TABLE IF NOT EXISTS ships. SQLite will not
# alter existing tables when only the CREATE script changes, so we patch them.
_SCHEMA_PATCHES: list[tuple[str, str, str]] = [
    ("properties", "max_occupancy", "INTEGER"),
    ("comps", "sleeps", "INTEGER"),
    ("price_recommendations", "recommended_min_stay", "INTEGER"),
    ("price_recommendations", "min_stay_source", "TEXT"),
    ("price_recommendations", "per_person_nightly", "REAL"),
]


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    for table, column, col_type in _SCHEMA_PATCHES:
        cols = {
            r["name"]
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db(db_path: Path | str | None = None, *, seed_markets: bool = True) -> Path:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(schema)
        _ensure_columns(conn)
        conn.commit()
        if seed_markets:
            from src.signals.store import SignalStore

            SignalStore(conn).seed_markets()
    return path
