#!/usr/bin/env python3
"""Backfill historical SNOTEL + Open-Meteo observations for Winter Park market.

Usage:
  python scripts/backfill_resort_history.py --from 2018-11-01 --to 2026-04-01
  python scripts/backfill_resort_history.py --db data/wp_pricing.db
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db import connect, init_db  # noqa: E402
from src.signals.collectors.snotel import SnotelCollector  # noqa: E402
from src.signals.collectors.weather import WeatherCollector  # noqa: E402
from src.signals.store import SignalStore  # noqa: E402


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def backfill(
    db_path: Path,
    start: date,
    end: date,
    market_id: str = "grand_home",
) -> dict[str, int]:
    init_db(db_path)
    counts = {"snotel_weeks": 0, "weather_weeks": 0}
    with connect(db_path) as conn:
        store = SignalStore(conn)
        store.seed_markets()
        snotel = SnotelCollector(store, sleep=lambda _s: None)
        weather = WeatherCollector(store, sleep=lambda _s: None)
        d = start
        while d <= end:
            print(f"Backfill week of {d.isoformat()}...", flush=True)
            sr = snotel.run(d, market_id)
            if sr.status != "failed":
                counts["snotel_weeks"] += 1
            wr = weather.run(d, market_id)
            if wr.status != "failed":
                counts["weather_weeks"] += 1
            d += timedelta(days=7)
    return counts


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill resort history signals")
    p.add_argument("--db", default=str(ROOT / "data" / "wp_pricing.db"))
    p.add_argument("--from", dest="start", default="2018-11-01")
    p.add_argument("--to", dest="end", default=None)
    p.add_argument("--market", default="grand_home")
    args = p.parse_args()
    end = parse_date(args.end) if args.end else date.today()
    start = parse_date(args.start)
    counts = backfill(Path(args.db), start, end, args.market)
    print(f"Backfill complete: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
