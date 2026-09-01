"""Access-risk feature builder (WP-08)."""

from __future__ import annotations

from datetime import date

from src.signals.store import SignalStore


def access_risk(store: SignalStore, market_id: str, as_of: date) -> float:
    """Latest Berthoud / US-40 access risk as of the pricing decision date."""
    row = store.latest_observation(
        as_of=as_of,
        signal_key="cdot.access_risk",
        market_id=market_id,
        effective_date=as_of,
    )
    if row is None or row["value"] is None:
        # Fall back to any recent observation on or before as_of.
        rows = store.read_observations(
            as_of=as_of,
            signal_key="cdot.access_risk",
            market_id=market_id,
            qualities=["ok"],
        )
        if not rows:
            return 0.0
        row = rows[-1]
    if row is None or row["value"] is None:
        return 0.0
    return float(row["value"])
