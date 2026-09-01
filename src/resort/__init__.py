"""Seed resort reference data (events, season stats) from config + CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.config import ROOT, load_resort_config
from src.signals.store import SignalStore

MONTHLY_STATS_CSV = ROOT / "data" / "resort" / "winter_park_monthly_stats.csv"


def seed_resort_reference(store: SignalStore, *, force_events: bool = False) -> dict[str, int]:
    """Load winter_park.yaml events and monthly stats if tables are empty."""
    cfg = load_resort_config()
    resort_id = cfg.get("resort_id", "winter_park")
    counts = {"events": 0, "stats": 0}

    existing = store.conn.execute(
        "SELECT COUNT(*) AS n FROM resort_events WHERE resort_id = ?", (resort_id,)
    ).fetchone()["n"]
    if existing == 0 or force_events:
        if force_events and existing:
            store.conn.execute(
                "DELETE FROM resort_events WHERE resort_id = ?", (resort_id,)
            )
            store.conn.commit()
        for ev in cfg.get("seed_events") or []:
            store.upsert_resort_event(
                resort_id=resort_id,
                event_date=ev["event_date"],
                event_type=ev["event_type"],
                entity_name=ev.get("entity_name"),
                notes=ev.get("notes"),
                source_url=ev.get("source_url"),
            )
            counts["events"] += 1
        for blk in cfg.get("ikon_blackouts") or []:
            store.upsert_resort_event(
                resort_id=resort_id,
                event_date=blk["start"],
                event_type="ikon_blackout",
                entity_name="Ikon Pass",
                notes=blk.get("notes"),
            )
            counts["events"] += 1

    stat_n = store.conn.execute(
        "SELECT COUNT(*) AS n FROM resort_season_stats WHERE resort_id = ?", (resort_id,)
    ).fetchone()["n"]
    if stat_n == 0 and MONTHLY_STATS_CSV.exists():
        with MONTHLY_STATS_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                month = int(row["month"])
                for key, unit in (
                    ("avg_snowfall_in", "inches"),
                    ("avg_base_depth_in", "inches"),
                    ("snowfall_days", "days"),
                ):
                    val = row.get(key)
                    if val:
                        store.upsert_season_stat(
                            resort_id=resort_id,
                            stat_key=key,
                            month=month,
                            season=None,
                            value=float(val),
                            unit=unit,
                            source=row.get("source", "onthesnow"),
                        )
                        counts["stats"] += 1

    return counts
