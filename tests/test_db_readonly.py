from __future__ import annotations

import sqlite3

import pytest

from src.db import connect_readonly, init_db


def test_readonly_connection_never_runs_schema_writes(tmp_path):
    path = tmp_path / "database with spaces.db"
    init_db(path)
    with connect_readonly(path) as conn:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE should_not_exist (id INTEGER)")
