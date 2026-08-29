"""Deliberately broken fixture collector — WP-02 acceptance."""

from __future__ import annotations

from datetime import date

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation


@register_collector
class BrokenFixtureCollector(Collector):
    """Returns an out-of-range value so the framework writes zero ok values + failed run."""

    schema = CollectorSchema(
        collector_id="broken_fixture",
        category="test",
        cadence="daily",
        source="fixture",
        fields=[
            FieldSpec("value", unit="ratio", value_min=0.0, value_max=1.0),
        ],
    )

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        key = self.schema.signal_key(self.schema.fields[0])
        return [
            Observation(
                signal_key=key,
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=99.0,  # out of range — must be rejected as failed, never clamped
                quality="ok",
            )
        ]
