"""Resort operations extractor (WP-07) — terrain open, lifts, ticket window.

LLM extractors are schema-bound: emit typed fields + source URL.
Out-of-range (terrain > 100%) is rejected as failed, never clamped.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE

# Default resort condition pages by market (extractor reads these URLs).
RESORT_SOURCES = {
    "grand_home": "https://www.winterparkresort.com/the-mountain/mountain-report",
    "summit": "https://www.breckenridge.com/the-mountain/mountain-report",
    "clear_creek_eagle": "https://www.vail.com/the-mountain/mountain-report.aspx",
}


@register_collector
class ResortCollector(Collector):
    schema = CollectorSchema(
        collector_id="resort",
        category="conditions",
        cadence="daily",
        source="resort_conditions_extractor",
        fields=[
            FieldSpec("terrain_open_pct", unit="percent", value_min=0.0, value_max=100.0),
            FieldSpec("lifts_open", unit="count", value_min=0.0, value_max=50.0),
            FieldSpec("trails_open", unit="count", value_min=0.0, value_max=300.0),
            FieldSpec("base_depth_in", unit="inches", value_min=0.0, value_max=200.0),
            FieldSpec("lift_ticket_window_usd", unit="usd", value_min=0.0, value_max=500.0),
        ],
    )

    def __init__(
        self,
        store,
        *,
        extract_fn: Callable[[str], dict[str, Any]] | None = None,
        fixture_path: Path | None = None,
        sleep=None,
    ):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.extract_fn = extract_fn
        self.fixture_path = fixture_path

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        url = RESORT_SOURCES.get(market_id)
        if self.fixture_path:
            payload = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
            data = payload.get(market_id) or payload
        elif self.extract_fn and url:
            data = self.extract_fn(url)
        else:
            return [
                Observation(
                    signal_key="resort.terrain_open_pct",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    provenance_url=url,
                    meta={"reason": "no_extractor_or_fixture"},
                )
            ]

        obs: list[Observation] = []
        mapping = {
            "terrain_open_pct": data.get("terrain_open_pct"),
            "lifts_open": data.get("lifts_open"),
            "trails_open": data.get("trails_open"),
            "base_depth_in": data.get("base_depth_in"),
            "lift_ticket_window_usd": data.get("lift_ticket_window_usd"),
        }
        src = data.get("source_url") or url
        for name, val in mapping.items():
            if val is None:
                continue
            obs.append(
                Observation(
                    signal_key=f"resort.{name}",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=float(val),
                    quality=QUALITY_OK,
                    provenance_url=src,
                    meta={"source_url": src},
                )
            )
        return obs
