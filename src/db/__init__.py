"""Database helpers (SQLite by default)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wp_pricing.db"

# Mirrors config/portfolio/mont_luxe.yaml. Fallback if that file cannot be read.
PROPERTY_OWNER_IDS: dict[str, str] = {
    "summit_haus": "northwoods",
    "overlook_ridge": "northwoods",
    "cloud_9": "cloud9",
}

# Columns added after initial CREATE TABLE IF NOT EXISTS ships. SQLite will not
# alter existing tables when only the CREATE script changes, so we patch them.
_SCHEMA_PATCHES: list[tuple[str, str, str]] = [
    ("properties", "max_occupancy", "INTEGER"),
    ("properties", "airbnb_room_id", "TEXT"),
    ("properties", "tenant_id", "TEXT NOT NULL DEFAULT 'mont_luxe_collection'"),
    ("properties", "owner_id", "TEXT"),
    ("properties", "market_id", "TEXT"),
    ("comps", "sleeps", "INTEGER"),
    ("price_recommendations", "recommended_min_stay", "INTEGER"),
    ("price_recommendations", "min_stay_source", "TEXT"),
    ("price_recommendations", "per_person_nightly", "REAL"),
    ("price_recommendations", "range_low", "REAL"),
    ("price_recommendations", "range_high", "REAL"),
    ("price_recommendations", "evidence_count", "INTEGER"),
    ("nightly_inventory", "booked_at", "TEXT"),
    ("nightly_inventory", "guest_count", "INTEGER"),
    ("rate_changes", "rule_version", "TEXT"),
    ("rate_changes", "model_version", "TEXT"),
    ("rate_changes", "inputs_hash", "TEXT"),
    ("rate_changes", "request_id", "TEXT"),
]


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    # WAL allows the scheduler/health CLI to read while a sync writes. Ignore
    # the result because some read-only filesystems reject changing journal mode.
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, website TEXT,
            timezone TEXT NOT NULL DEFAULT 'America/Denver',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO tenants (tenant_id, name, website)
        VALUES ('mont_luxe_collection', 'Mont Luxe Collection', 'https://montluxecollection.com');
        """
    )
    _ensure_columns(conn)
    _ensure_reservations_table(conn)
    conn.commit()
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _ensure_columns(conn: sqlite3.Connection) -> None:
    for table, column, col_type in _SCHEMA_PATCHES:
        if not _table_exists(conn, table):
            continue
        cols = {
            r["name"]
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    _backfill_recommendation_inputs_hash(conn)
    if _table_exists(conn, "properties"):
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_properties_airbnb_room ON properties(airbnb_room_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_properties_owner ON properties(owner_id)"
        )
        _seed_owner_ids(conn)
        _backfill_market_ids(conn)


def _backfill_recommendation_inputs_hash(conn: sqlite3.Connection) -> None:
    """Existing rows predate NOT NULL on price_recommendations.inputs_hash."""
    if not _table_exists(conn, "price_recommendations"):
        return
    cols = {
        r["name"]
        for r in conn.execute("PRAGMA table_info(price_recommendations)").fetchall()
    }
    if "inputs_hash" not in cols:
        return
    conn.execute(
        """
        UPDATE price_recommendations
        SET inputs_hash = 'legacy-missing'
        WHERE inputs_hash IS NULL OR inputs_hash = ''
        """
    )


def _ensure_reservations_table(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "properties"):
        return
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            reservation_id  TEXT PRIMARY KEY,
            property_id     TEXT NOT NULL,
            listing_id      TEXT,
            check_in        TEXT NOT NULL,
            check_out       TEXT NOT NULL,
            nights          INTEGER,
            status          TEXT,
            source          TEXT,
            confirmed_at    TEXT,
            created_at_pms  TEXT,
            guest_count     INTEGER,
            fare_accommodation REAL,
            nightly_rate    REAL,
            raw_json        TEXT,
            synced_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_reservations_property
            ON reservations(property_id, check_in);
        CREATE TABLE IF NOT EXISTS sync_runs (
            run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at TEXT, status TEXT NOT NULL DEFAULT 'running',
            listings INTEGER NOT NULL DEFAULT 0, calendar_nights INTEGER NOT NULL DEFAULT 0,
            reservations INTEGER NOT NULL DEFAULT 0, errors TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS pms_webhook_events (
            event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, listing_id TEXT,
            start_date TEXT, end_date TEXT, payload_json TEXT NOT NULL,
            received_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_webhook_listing_dates
            ON pms_webhook_events(listing_id, start_date, end_date);
        """
    )


def _owner_mapping() -> dict[str, str]:
    mapping = dict(PROPERTY_OWNER_IDS)
    try:
        from src.config import load_portfolio_config

        cfg = load_portfolio_config()
        for pid, spec in (cfg.get("properties") or {}).items():
            oid = (spec or {}).get("owner_id")
            if pid and oid:
                mapping[str(pid)] = str(oid)
    except Exception:
        pass
    return mapping


def _seed_owner_ids(conn: sqlite3.Connection) -> None:
    """Fill known live properties when owner_id is still empty. Never overwrite."""
    if not _table_exists(conn, "properties"):
        return
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(properties)").fetchall()}
    if "owner_id" not in cols:
        return
    for property_id, owner_id in _owner_mapping().items():
        conn.execute(
            """
            UPDATE properties
            SET owner_id = ?
            WHERE property_id = ?
              AND (owner_id IS NULL OR owner_id = '')
            """,
            (owner_id, property_id),
        )


def _backfill_market_ids(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(properties)").fetchall()}
    if "market_id" not in cols:
        return
    conn.execute(
        """
        UPDATE properties
        SET market_id = 'grand_home'
        WHERE market_id IS NULL OR market_id = ''
        """
    )
    try:
        from src.config import load_portfolio_config

        cfg = load_portfolio_config()
        for pid, spec in (cfg.get("properties") or {}).items():
            mid = (spec or {}).get("market_id")
            if pid and mid:
                conn.execute(
                    """
                    UPDATE properties SET market_id = ?
                    WHERE property_id = ? AND (market_id IS NULL OR market_id = '')
                    """,
                    (str(mid), str(pid)),
                )
    except Exception:
        pass


def list_owner_ids(conn: sqlite3.Connection) -> list[str]:
    if not _table_exists(conn, "properties"):
        return []
    return [
        r["owner_id"]
        for r in conn.execute(
            """
            SELECT DISTINCT owner_id FROM properties
            WHERE owner_id IS NOT NULL AND owner_id != ''
            ORDER BY owner_id
            """
        ).fetchall()
    ]


def property_ids_for_owner(conn: sqlite3.Connection, owner_id: str) -> list[str]:
    return [
        r["property_id"]
        for r in conn.execute(
            """
            SELECT property_id FROM properties
            WHERE owner_id = ?
            ORDER BY property_id
            """,
            (owner_id,),
        ).fetchall()
    ]


def resolve_property_ids(
    conn: sqlite3.Connection,
    property_ids: list[str] | None = None,
    owner_id: str | None = None,
) -> list[str] | None:
    """Intersect --property and --owner. None means the full portfolio.

    Raises ValueError if --owner matches no properties.
    """
    if not owner_id:
        return property_ids
    owned = property_ids_for_owner(conn, owner_id)
    if not owned:
        known = list_owner_ids(conn)
        raise ValueError(
            f"No properties for owner {owner_id!r}. "
            f"Known owner_id values: {known or '(none)'}"
        )
    if property_ids:
        wanted = set(property_ids)
        missing = [pid for pid in property_ids if pid not in set(owned)]
        if missing:
            raise ValueError(
                f"Properties {missing} are not assigned to owner {owner_id!r} "
                f"(owner has {owned})"
            )
        return [pid for pid in owned if pid in wanted]
    return owned


def init_db(db_path: Path | str | None = None, *, seed_markets: bool = True) -> Path:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(schema)
        _ensure_columns(conn)
        _ensure_reservations_table(conn)
        _seed_owner_ids(conn)
        _backfill_market_ids(conn)
        conn.commit()
        if seed_markets:
            from src.signals.store import SignalStore

            store = SignalStore(conn)
            store.seed_markets()
            from src.resort import seed_resort_reference

            seed_resort_reference(store)
    return path
