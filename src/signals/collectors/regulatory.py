"""STR licence / regulatory tracker (WP-10).

Licence issuance leads listing appearance by 6–12 months.
Missing machine-readable source → unavailable, never estimated.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE


@register_collector
class RegulatoryCollector(Collector):
    schema = CollectorSchema(
        collector_id="regulatory",
        category="supply",
        cadence="monthly",
        source="jurisdiction_licence_portals",
        fields=[
            FieldSpec("str_licence_count", unit="count", value_min=0.0, value_max=50000.0),
            FieldSpec("lodging_tax_rate", unit="ratio", value_min=0.0, value_max=0.5),
        ],
    )

    def __init__(self, store, *, fixture_path: Path | None = None, sleep=None):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_path = fixture_path

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        if not self.fixture_path:
            return [
                Observation(
                    signal_key="regulatory.str_licence_count",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.replace(day=1).isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    meta={"reason": "no_machine_readable_source"},
                )
            ]
        data = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
        row = data.get(market_id) or {}
        obs = []
        if "str_licence_count" in row:
            obs.append(
                Observation(
                    signal_key="regulatory.str_licence_count",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.replace(day=1).isoformat(),
                    value=float(row["str_licence_count"]),
                    quality=QUALITY_OK,
                    provenance_url=row.get("source_url"),
                )
            )
        if "lodging_tax_rate" in row:
            obs.append(
                Observation(
                    signal_key="regulatory.lodging_tax_rate",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.replace(day=1).isoformat(),
                    value=float(row["lodging_tax_rate"]),
                    quality=QUALITY_OK,
                    provenance_url=row.get("source_url"),
                )
            )
        if not obs:
            obs.append(
                Observation(
                    signal_key="regulatory.str_licence_count",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.replace(day=1).isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    meta={"reason": "market_missing_from_fixture"},
                )
            )
        return obs
