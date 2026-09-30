"""Consumer indicators. They are registered at shadow and are not price inputs by themselves.

`models.demand_shifts_price` may read `macro.consumer_confidence` when that flag
is on. Nothing in this module promotes a definition to active.
"""

from __future__ import annotations

import sqlite3

from src.signals.store import SignalDefinition, SignalStore

# Keys from dossier 3. Descriptions stay short; the dossier has the sources.
CONSUMER_INDICATORS: tuple[tuple[str, str, str, str], ...] = (
    ("macro.consumer_confidence", "macro", "z", "Consumer sentiment, standardized"),
    ("macro.den_passengers", "macro", "index", "Denver airport passenger index"),
    ("macro.eia_gasoline", "macro", "usd_per_gallon", "EIA gasoline price"),
    ("macro.enso_oni", "macro", "celsius", "ENSO ocean index"),
    ("demand.listing_supply_index", "demand", "index", "Listing supply versus a baseline"),
)


def register_consumer_indicators(conn: sqlite3.Connection) -> list[str]:
    """Insert each indicator at shadow. A definition that already exists keeps its status."""
    store = SignalStore(conn)
    keys: list[str] = []
    for signal_key, category, unit, description in CONSUMER_INDICATORS:
        existing = store.get_definition(signal_key)
        store.upsert_definition(
            SignalDefinition(
                signal_key=signal_key,
                category=category,
                unit=unit,
                cadence="monthly",
                source="dossier_3",
                status="shadow",
                description=description,
                collector="consumer",
            )
        )
        if existing is None:
            store.set_status(signal_key, "shadow")
        row = store.get_definition(signal_key)
        if row is None:
            raise RuntimeError(f"{signal_key} was not registered")
        if existing is None and row["status"] != "shadow":
            raise RuntimeError(f"{signal_key} must start at shadow, got {row['status']}")
        keys.append(signal_key)
    return keys
