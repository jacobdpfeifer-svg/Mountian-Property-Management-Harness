"""SQLite sidecar connection. Foreign keys on. No pricing tables."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.memory.paths import ensure_layout

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DB_NAME = "operator_memory.db"


def connect_memory(root: Path | None = None) -> sqlite3.Connection:
    layout = ensure_layout(root)
    conn = sqlite3.connect(str(layout / DB_NAME))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        # A private store on a read-only/removable filesystem should fail on the
        # next write, not silently relax its foreign-key or transaction contract.
        pass
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def memory_db_path(root: Path | None = None) -> Path:
    return ensure_layout(root) / DB_NAME
