"""Calendar intelligence (WP-09) — school calendars, events, WP Express.

Replaces hand-maintained events.yaml as the sourced table of demand windows.
After each run, upserts ok `calendars.demand_strength` rows into the legacy
`demand_signals` table so WP-05 `demand_tier` / ceiling keep working.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.signals.collector import (
    Collector,
    CollectorResult,
    CollectorSchema,
    FieldSpec,
    register_collector,
)
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

    def run(
        self,
        as_of: date,
        market_id: str,
        *,
        retries: int = 2,
        backoff_s: float = 0.5,
    ) -> CollectorResult:
        result = super().run(as_of, market_id, retries=retries, backoff_s=backoff_s)
        if result.status != "failed":
            self._sync_demand_signals(result.run_id, market_id)
        return result

    def _sync_demand_signals(self, run_id: str, market_id: str) -> None:
        """Keep demand_signals read-compat shim populated for ceiling demand_tier."""
        rows = self.store.conn.execute(
            """
            SELECT effective_date, value, meta_json
            FROM signal_observations
            WHERE run_id = ?
              AND signal_key = 'calendars.demand_strength'
              AND quality = 'ok'
              AND value IS NOT NULL
            """,
            (run_id,),
        ).fetchall()
        # Home market maps to the legacy region key used by sample CSV / engine.
        region = "winter_park" if market_id == "grand_home" else market_id
        for row in rows:
            meta: dict[str, Any] = {}
            raw = row["meta_json"]
            if raw:
                try:
                    meta = json.loads(raw) if isinstance(raw, str) else dict(raw)
                except (TypeError, json.JSONDecodeError):
                    meta = {}
            event = str(meta.get("event") or "calendar")
            self.store.conn.execute(
                """
                INSERT INTO demand_signals (
                    signal_date, region, event_name, signal_strength, source
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(signal_date, region, event_name) DO UPDATE SET
                    signal_strength=excluded.signal_strength,
                    source=excluded.source
                """,
                (
                    row["effective_date"],
                    region,
                    event,
                    float(row["value"]),
                    "calendars",
                ),
            )
        if rows:
            self.store.conn.commit()

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
