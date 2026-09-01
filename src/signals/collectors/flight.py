"""Flight demand proxy — DEN-origin seat capacity YoY (Track B2)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE


@register_collector
class FlightCollector(Collector):
    schema = CollectorSchema(
        collector_id="flight",
        category="demand_intent",
        cadence="monthly",
        source="bts_t100",
        fields=[
            FieldSpec(
                "den_capacity_yoy",
                unit="ratio",
                value_min=-1.0,
                value_max=1.0,
                description="YoY change DEN→mountain air capacity",
            ),
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
        if market_id != "grand_home":
            return []
        if not self.fixture_path:
            return [
                Observation(
                    signal_key="flight.den_capacity_yoy",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    meta={"reason": "bts_fixture_required_brief_only_mode"},
                )
            ]
        payload = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
        month = as_of.strftime("%Y-%m")
        data = payload.get(month) or payload.get("default") or {}
        yoy = float(data.get("den_capacity_yoy", 0.0))
        return [
            Observation(
                signal_key="flight.den_capacity_yoy",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=yoy,
                quality=QUALITY_OK,
                meta={"month": month, "source": "bts_t100_fixture"},
            )
        ]
