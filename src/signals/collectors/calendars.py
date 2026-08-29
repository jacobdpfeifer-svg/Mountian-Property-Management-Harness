"""Calendar intelligence (WP-09) — school calendars, events, WP Express.

Replaces hand-maintained events.yaml as the sourced table of demand windows.
Keeps demand_signals read-compat shim populated for WP-05 demand_tier.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK


@register_collector
class CalendarsCollector(Collector):
    schema = CollectorSchema(
        collector_id="calendars",
        category="demand_intent",
        cadence="annual",
        source="school_and_resort_calendars",
        fields=[
            FieldSpec("demand_strength", unit="ratio", value_min=0.0, value_max=1.0),
            FieldSpec("wp_express_sellout", unit="flag", value_min=0.0, value_max=1.0),
        ],
    )

    def __init__(self, store, *, fixture_path: Path | None = None, sleep=None):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_path = fixture_path

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        path = self.fixture_path or (
            Path(__file__).resolve().parents[3]
            / "config"
            / "policies"
            / "calendar_signals.json"
        )
        if not path.exists():
            # Fall back to events.yaml expansion via config.
            from src.config import load_events
            from src.features import _demand_index

            index = _demand_index(load_events())
            obs: list[Observation] = []
            for d, (strength, name) in index.items():
                if abs((d - as_of).days) > 400:
                    continue
                obs.append(
                    Observation(
                        signal_key="calendars.demand_strength",
                        market_id=market_id,
                        observed_at=min(as_of, d).isoformat(),
                        effective_date=d.isoformat(),
                        value=float(strength),
                        quality=QUALITY_OK,
                        provenance_url="config/policies/events.yaml",
                        meta={"event": name},
                    )
                )
            return obs

        data = json.loads(path.read_text(encoding="utf-8"))
        obs = []
        for ev in data.get("events") or []:
            start = date.fromisoformat(ev["start"])
            end = date.fromisoformat(ev["end"])
            strength = float(ev["signal_strength"])
            url = ev.get("source_url") or "calendar"
            d = start
            while d <= end:
                obs.append(
                    Observation(
                        signal_key="calendars.demand_strength",
                        market_id=market_id,
                        observed_at=min(as_of, start).isoformat(),
                        effective_date=d.isoformat(),
                        value=strength,
                        quality=QUALITY_OK,
                        provenance_url=url,
                        meta={"event": ev.get("name"), "district": ev.get("district")},
                    )
                )
                d += timedelta(days=1)
        for row in data.get("wp_express") or []:
            d = date.fromisoformat(row["date"])
            obs.append(
                Observation(
                    signal_key="calendars.wp_express_sellout",
                    market_id=market_id,
                    observed_at=min(as_of, d).isoformat(),
                    effective_date=d.isoformat(),
                    value=float(row.get("sellout", 0)),
                    quality=QUALITY_OK,
                    provenance_url=row.get("source_url") or "amtrak",
                    meta={"train": "Winter Park Express"},
                )
            )
        return obs
