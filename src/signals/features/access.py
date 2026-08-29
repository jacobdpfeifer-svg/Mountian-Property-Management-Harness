"""Access-risk feature builder (WP-08)."""

from __future__ import annotations

from datetime import date

from src.signals.store import SignalStore


def access_risk(store: SignalStore, market_id: str, target_date: date, as_of: date) -> float:
    row = store.latest_observation(
        as_of=as_of,
        signal_key="cdot.access_risk",
        market_id=market_id,
        effective_date=target_date,
    )
    if row is None or row["value"] is None:
        return 0.0
    return float(row["value"])
