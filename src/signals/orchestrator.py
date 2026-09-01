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
    ("intent", ["grand_home"]),
    ("flight", ["grand_home"]),
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

    # Build resort ops forecast features for home market after collectors finish.
    try:
        from src.signals.features.resort_ops import write_resort_ops_features

        label = write_resort_ops_features(store, "grand_home", as_of, as_of)
        snap = store.latest_resort_snapshot(as_of=as_of, market_id="grand_home")
        report["resort_ops"] = {
            "surface_label": label,
            "built_for": as_of.isoformat(),
            "snapshot": (
                {
                    "as_of": snap["as_of"],
                    "lift_open": snap["lift_open"],
                    "lift_total": snap["lift_total"],
                    "trail_open": snap["trail_open"],
                    "trail_total": snap["trail_total"],
                }
                if snap
                else None
            ),
        }
    except Exception as exc:  # noqa: BLE001
        report["failures"].append(f"resort_ops/grand_home: {exc}")

    return report
