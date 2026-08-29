"""ENSO / ONI collector (WP-03b) — season-ahead SQI prior from NOAA CPC.

Christmas prices are set in October, before meaningful snowpack exists.
With one season of local history you cannot forecast SQI from own data;
ONI is one of the only free genuine season-ahead priors. Monthly cadence.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import requests

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE

ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"


def parse_oni_ascii(text: str) -> list[tuple[int, str, float]]:
    """Parse CPC ONI ascii into (year, season_code, oni)."""
    rows: list[tuple[int, str, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("SEAS") or line.upper().startswith("YEAR"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            year = int(parts[0])
            seas = parts[1]
            oni = float(parts[2])
        except ValueError:
            continue
        rows.append((year, seas, oni))
    return rows


def oni_for_as_of(rows: list[tuple[int, str, float]], as_of: date) -> tuple[str, float] | None:
    """Latest ONI season fully known by as_of (conservative: prior completed season)."""
    # Seasons are 3-month: DJF ends Feb, etc. Map month -> last completed code.
    # Simplified: take the last row with year < as_of.year, or same year if month >= 3.
    if not rows:
        return None
    eligible = [r for r in rows if r[0] < as_of.year or (r[0] == as_of.year and as_of.month >= 3)]
    if not eligible:
        eligible = rows[:1]
    year, seas, oni = eligible[-1]
    return f"{year}-{seas}", oni


@register_collector
class EnsoCollector(Collector):
    schema = CollectorSchema(
        collector_id="enso",
        category="conditions",
        cadence="monthly",
        source="noaa_cpc_oni",
        fields=[
            FieldSpec("oni", unit="celsius_anomaly", value_min=-3.0, value_max=3.0,
                      description="Oceanic Niño Index"),
            FieldSpec("sqi_prior", unit="ratio", value_min=0.5, value_max=1.5,
                      description="Season-ahead SQI prior mapped from ONI"),
        ],
    )

    def __init__(self, store, *, fixture_text: str | None = None, fixture_path: Path | None = None,
                 sleep=None):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_text = fixture_text
        self.fixture_path = fixture_path

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        # ENSO is basin-scale; same value applies to all markets.
        try:
            if self.fixture_text is not None:
                text = self.fixture_text
            elif self.fixture_path:
                text = Path(self.fixture_path).read_text(encoding="utf-8")
            else:
                r = requests.get(ONI_URL, timeout=30)
                r.raise_for_status()
                text = r.text
        except requests.RequestException as exc:
            return [
                Observation(
                    signal_key="enso.oni",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    provenance_url=ONI_URL,
                    meta={"error": str(exc)},
                )
            ]

        rows = parse_oni_ascii(text)
        got = oni_for_as_of(rows, as_of)
        if got is None:
            return [
                Observation(
                    signal_key="enso.oni",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    provenance_url=ONI_URL,
                )
            ]
        label, oni = got
        # La Niña (negative ONI) tends to favor northern Colorado snow — mild prior.
        # Policy-declared mapping, not a fitted finding. Clamp via FieldSpec.
        prior = 1.0 - 0.08 * oni  # La Niña (oni<0) → prior > 1
        prior = max(0.5, min(1.5, prior))
        # effective_date = as_of; horizon covers season-ahead Christmas from October.
        christmas = date(as_of.year if as_of.month <= 12 else as_of.year, 12, 25)
        if as_of.month >= 1 and as_of.month <= 9:
            christmas = date(as_of.year, 12, 25)
        horizon = max(0, (christmas - as_of).days)
        return [
            Observation(
                signal_key="enso.oni",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=as_of.isoformat(),
                value=oni,
                horizon_days=0,
                quality=QUALITY_OK,
                provenance_url=ONI_URL,
                meta={"season": label},
            ),
            Observation(
                signal_key="enso.sqi_prior",
                market_id=market_id,
                observed_at=as_of.isoformat(),
                effective_date=christmas.isoformat(),
                value=prior,
                horizon_days=horizon,
                quality=QUALITY_OK,
                provenance_url=ONI_URL,
                meta={"season": label, "oni": oni, "mapping": "1.0 - 0.08*ONI"},
            ),
        ]
