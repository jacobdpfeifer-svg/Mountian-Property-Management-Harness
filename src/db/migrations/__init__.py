"""Ordered, checksummed SQL migrations for the data spine.

`init_db` keeps owning the legacy schema. Spine migrations are applied only by an
explicit call (`apply_migrations`), so the operator database never changes as a
side effect of a daily job. Applying them to the live database is an operator
step (docs/runbooks/DEPLOYMENT.md); here it is proven on local/test databases.

Each file is `NNNN_name.sql`. Its sha256 is recorded in `schema_migrations`; if a
file that was already applied later changes, `apply_migrations` refuses to run.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent
_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


class MigrationDrift(RuntimeError):
    """An applied migration's file no longer matches its recorded checksum."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    found = []
    for path in sorted(directory.glob("*.sql")):
        m = _NAME.match(path.name)
        if not m:
            raise ValueError(f"migration file name must be NNNN_name.sql: {path.name}")
        found.append(Migration(int(m.group(1)), m.group(2), path))
    versions = [m.version for m in found]
    if versions != list(range(1, len(found) + 1)):
        raise ValueError(f"migration versions must be contiguous from 1, got {versions}")
    return found


def schema_version(directory: Path = MIGRATIONS_DIR) -> str:
    """Release identifier for the spine schema: highest version + combined hash."""
    migrations = discover(directory)
    digest = hashlib.sha256("".join(m.sha256 for m in migrations).encode()).hexdigest()
    top = migrations[-1].version if migrations else 0
    return f"{top:04d}-{digest[:12]}"


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version    INTEGER PRIMARY KEY,
               name       TEXT NOT NULL,
               sha256     TEXT NOT NULL,
               applied_at TEXT NOT NULL
           )"""
    )


def applied(conn: sqlite3.Connection) -> dict[int, str]:
    _ensure_table(conn)
    return {int(r[0]): str(r[1]) for r in conn.execute("SELECT version, sha256 FROM schema_migrations")}


def pending(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    done = applied(conn)
    for m in discover(directory):
        if m.version in done and done[m.version] != m.sha256:
            raise MigrationDrift(
                f"migration {m.version:04d}_{m.name} changed after it was applied "
                f"(recorded {done[m.version][:12]}, file {m.sha256[:12]}); add a new migration instead"
            )
    return [m for m in discover(directory) if m.version not in done]


def apply_migrations(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply every pending migration, each in its own transaction. Returns versions applied."""
    todo = pending(conn, directory)
    done: list[int] = []
    for m in todo:
        # executescript commits implicitly; wrap explicitly so a failing statement
        # leaves neither partial DDL nor a schema_migrations row behind.
        script = (
            "BEGIN;\n" + m.sql + "\nINSERT INTO schema_migrations (version, name, sha256, applied_at) "
            f"VALUES ({m.version}, '{m.name}', '{m.sha256}', "
            f"'{datetime.now(timezone.utc).isoformat(timespec='seconds')}');\nCOMMIT;"
        )
        try:
            conn.executescript(script)
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        done.append(m.version)
    return done
