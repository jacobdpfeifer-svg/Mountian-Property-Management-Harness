"""CDOT / Berthoud Pass access risk (WP-08).

US-40 over Berthoud is the only direct Denver route. Closures and chain laws
are a same-week demand cliff no competitor-price feed can observe.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE

COTRIP_URL = "https://www.cotrip.org/"


@register_collector
class CdotCollector(Collector):
    schema = CollectorSchema(
        collector_id="cdot",
        category="access",
        cadence="hourly",
        source="cotrip",
        fields=[
            FieldSpec("berthoud_closed", unit="flag", value_min=0.0, value_max=1.0),
            FieldSpec("chain_law", unit="flag", value_min=0.0, value_max=1.0),
            FieldSpec("access_risk", unit="ratio", value_min=0.0, value_max=1.0),
        ],
    )

    def __init__(self, store, *, fixture_path: Path | None = None, sleep=None):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_path = fixture_path

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        if market_id not in ("grand_home", "grand_valley"):
            # Berthoud primarily affects Grand County home/valley.
            return []
        if not self.fixture_path:
            # Live CoTrip parser not wired — unavailable, never invent 0/closed.
            return [
                Observation(
                    signal_key="cdot.access_risk",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    provenance_url=COTRIP_URL,
                    meta={"reason": "live_cotrip_not_wired_use_fixture"},
                )
            ]
        data = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
        day = data.get(as_of.isoformat()) or data.get("default") or {}
        closed = float(day.get("berthoud_closed", 0))
        chain = float(day.get("chain_law", 0))
        risk = min(1.0, closed * 1.0 + chain * 0.4)
        return [
            Observation(
                signal_key="cdot.berthoud_closed",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=closed,
                quality=QUALITY_OK,
                provenance_url=COTRIP_URL,
            ),
            Observation(
                signal_key="cdot.chain_law",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=chain,
                quality=QUALITY_OK,
                provenance_url=COTRIP_URL,
            ),
            Observation(
                signal_key="cdot.access_risk",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=risk,
                quality=QUALITY_OK,
                provenance_url=COTRIP_URL,
            ),
        ]
