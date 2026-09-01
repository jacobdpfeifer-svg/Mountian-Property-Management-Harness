"""Intent / search-interest collector (WP-12 / Track B1)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE


def _z_score(values: list[float], current: float) -> float:
    if len(values) < 3:
        return 0.0
    mu = mean(values)
    sigma = pstdev(values) or 1.0
    return (current - mu) / sigma


@register_collector
class IntentCollector(Collector):
    schema = CollectorSchema(
        collector_id="intent",
        category="demand_intent",
        cadence="weekly",
        source="trends_api",
        fields=[
            FieldSpec("search_interest", unit="index", value_min=-5.0, value_max=5.0),
        ],
    )

    def __init__(
        self,
        store,
        *,
        fixture_path: Path | None = None,
        sleep=None,
    ):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_path = fixture_path

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        if self.fixture_path:
            payload = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
            data = payload.get(market_id) or payload.get(as_of.isoformat()) or payload
            raw = float(data.get("search_interest", data.get("raw_index", 0)))
            history = [float(x) for x in data.get("history", [raw])]
            z = _z_score(history, raw)
            return [
                Observation(
                    signal_key="intent.search_interest",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=z,
                    quality=QUALITY_OK,
                    meta={"raw_index": raw, "z_score": z},
                )
            ]
        return [
            Observation(
                signal_key="intent.search_interest",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=None,
                quality=QUALITY_UNAVAILABLE,
                meta={"reason": "use_fixture_or_enable_trends_fetch"},
            )
        ]
