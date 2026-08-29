"""Cadence-aware signal orchestration (WP-14)."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.signals.collector import get_collector, list_collectors
from src.signals.store import SignalStore

# Staggered daily cycle — collectors never write prices.
DEFAULT_SCHEDULE = [
    ("snotel", ["grand_home", "grand_valley", "summit", "clear_creek_eagle", "routt"]),
    ("enso", ["grand_home"]),
    ("weather", ["grand_home", "summit"]),
    ("cdot", ["grand_home"]),
    ("calendars", ["grand_home"]),
    ("resort", ["grand_home"]),
    ("regulatory", ["grand_home", "grand_valley"]),
]


def run_daily_cycle(
    store: SignalStore,
    as_of: date,
    *,
    schedule: list[tuple[str, list[str]]] | None = None,
    collector_kwargs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    import src.signals.collectors  # noqa: F401 — register

    schedule = schedule or DEFAULT_SCHEDULE
    collector_kwargs = collector_kwargs or {}
    report: dict[str, Any] = {"as_of": as_of.isoformat(), "runs": [], "failures": []}

    for collector_id, markets in schedule:
        if collector_id not in list_collectors():
            report["failures"].append(f"unknown collector {collector_id}")
            continue
        cls = get_collector(collector_id)
        kwargs = collector_kwargs.get(collector_id, {})
        coll = cls(store, **kwargs)
        for market_id in markets:
            try:
                result = coll.run(as_of, market_id)
                report["runs"].append(
                    {
                        "collector": collector_id,
                        "market_id": market_id,
                        "run_id": result.run_id,
                        "status": result.status,
                        "written": result.written,
                        "rejected": result.rejected,
                        "errors": result.errors[:5],
                    }
                )
                if result.status == "failed":
                    report["failures"].append(
                        f"{collector_id}/{market_id}: {result.errors[:2]}"
                    )
            except Exception as exc:  # noqa: BLE001
                report["failures"].append(f"{collector_id}/{market_id}: {exc}")
    return report
