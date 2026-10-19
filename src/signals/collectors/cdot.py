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

COTRIP_URL = "https://api-511x-co.carsprogram.org/events/map-features"


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
            # Experimental. Not read by src/signals/features/access.py.
            FieldSpec(
                "i70_east_shared_negative", unit="flag", value_min=0.0, value_max=1.0,
                description="I-70 full closure east of Empire. Experimental; not a price input.",
            ),
            FieldSpec(
                "i70_west_substitution", unit="flag", value_min=0.0, value_max=1.0,
                description="I-70 full closure west of Empire. Experimental; not a price input.",
            ),
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
        i70_east = 0.0
        i70_west = 0.0
        if self.fixture_path:
            data = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
            day = data.get(as_of.isoformat()) or data.get("default") or {}
            closed = float(day.get("berthoud_closed", 0))
            chain = float(day.get("chain_law", 0))
            risk = min(1.0, closed * 1.0 + chain * 0.4)
            i70_east = float(day.get("i70_east_shared_negative", 0))
            i70_west = float(day.get("i70_west_substitution", 0))
        else:
            try:
                parsed = self.fetch_fn()
                if parsed.get("quality") != "ok":
                    return [
                        Observation(
                            signal_key=key,
                            market_id=market_id,
                            observed_at=as_of.isoformat(),
                            effective_date=as_of.isoformat(),
                            value=None,
                            quality=QUALITY_UNAVAILABLE,
                            provenance_url=COTRIP_URL,
                            meta={"reason": parsed.get("reason", "cotrip_unavailable")},
                        )
                        for key in (
                            "cdot.berthoud_closed",
                            "cdot.chain_law",
                            "cdot.access_risk",
                            "cdot.i70_east_shared_negative",
                            "cdot.i70_west_substitution",
                        )
                    ]
                closed = float(parsed["berthoud_closed"])
                chain = float(parsed["chain_law"])
                risk = float(parsed["access_risk"])
                i70_east = float(parsed.get("i70_east_shared_negative") or 0.0)
                i70_west = float(parsed.get("i70_west_substitution") or 0.0)
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
            Observation(
                signal_key="cdot.i70_east_shared_negative",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=i70_east,
                quality=QUALITY_OK,
                provenance_url=COTRIP_URL,
            ),
            Observation(
                signal_key="cdot.i70_west_substitution",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=i70_west,
                quality=QUALITY_OK,
                provenance_url=COTRIP_URL,
            ),
        ]
