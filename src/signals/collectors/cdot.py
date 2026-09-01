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
from src.signals.extractors.cotrip import fetch_cotrip_access
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

    def __init__(
        self,
        store,
        *,
        fixture_path: Path | None = None,
        fetch_fn=None,
        sleep=None,
    ):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_path = fixture_path
        self.fetch_fn = fetch_fn or fetch_cotrip_access

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        if market_id not in ("grand_home", "grand_valley"):
            # Berthoud primarily affects Grand County home/valley.
            return []
        if self.fixture_path:
            data = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
            day = data.get(as_of.isoformat()) or data.get("default") or {}
            closed = float(day.get("berthoud_closed", 0))
            chain = float(day.get("chain_law", 0))
            risk = min(1.0, closed * 1.0 + chain * 0.4)
        else:
            try:
                parsed = self.fetch_fn()
                closed = float(parsed["berthoud_closed"])
                chain = float(parsed["chain_law"])
                risk = float(parsed["access_risk"])
            except Exception as exc:  # noqa: BLE001 — degrade, never invent zeros
                return [
                    Observation(
                        signal_key="cdot.access_risk",
                        market_id=market_id,
                        observed_at=as_of.isoformat(),
                        effective_date=as_of.isoformat(),
                        value=None,
                        quality=QUALITY_UNAVAILABLE,
                        provenance_url=COTRIP_URL,
                        meta={"reason": "cotrip_fetch_failed", "error": str(exc)[:200]},
                    )
                ]
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
