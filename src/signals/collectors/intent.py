"""Intent signals (WP-12) — first cut / lowest priority. EXPERIMENTAL only."""

from __future__ import annotations

from datetime import date

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_UNAVAILABLE


@register_collector
class IntentCollector(Collector):
    schema = CollectorSchema(
        collector_id="intent",
        category="demand_intent",
        cadence="weekly",
        source="trends_api",
        fields=[
            FieldSpec("search_interest", unit="index", value_min=0.0, value_max=100.0),
        ],
    )

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        return [
            Observation(
                signal_key="intent.search_interest",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=None,
                quality=QUALITY_UNAVAILABLE,
                meta={"reason": "deferred_wp12_first_cut"},
            )
        ]
