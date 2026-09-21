"""Resort operations collector — terrain, lifts, grooming via Intrawest feed + HTML fallback."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.extractors.intrawest import (
    WINTER_PARK_FEED_ID,
    fetch_intrawest_lifts,
    parse_intrawest_payload,
)
from src.signals.extractors.winter_park_resort import fetch_resort_report
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE

# Intrawest feed IDs and HTML fallbacks by market.
# NB: values are deliberately heterogeneous (feed_id is an int, html_url a str) — an
# unannotated literal here makes mypy widen every per-market dict to `object`, which
# turns every `cfg.get(...)` below into a false "object has no attribute get". Annotate
# explicitly instead of resorting to `Any`, so a real shape error still gets caught.
RESORT_SOURCES: dict[str, dict[str, str | int]] = {
    "grand_home": {
        "feed_id": WINTER_PARK_FEED_ID,
        "html_url": "https://www.winterparkresort.com/the-mountain/mountain-report",
    },
    "summit": {
        "html_url": "https://www.breckenridge.com/the-mountain/mountain-report",
    },
    "clear_creek_eagle": {
        "html_url": "https://www.vail.com/the-mountain/mountain-report.aspx",
    },
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
            FieldSpec("lifts_on_hold", unit="count", value_min=0.0, value_max=50.0),
            FieldSpec("trails_groomed_pct", unit="percent", value_min=0.0, value_max=100.0),
            FieldSpec("resort_open", unit="flag", value_min=0.0, value_max=1.0),
            FieldSpec("surface_packed_score", unit="ratio", value_min=0.0, value_max=1.0),
        ],
    )

    def __init__(
        self,
        store,
        *,
        extract_fn: Callable[[str], dict[str, Any]] | None = None,
        # NB: this is always called as `self.intrawest_fn(cfg["feed_id"])` below
        # (never with zero args) — the signature previously said `Callable[[], ...]`,
        # which every real caller of the default (`fetch_intrawest_lifts`) violated.
        intrawest_fn: Callable[[int], list[dict[str, Any]]] | None = None,
        fixture_path: Path | None = None,
        intrawest_fixture_path: Path | None = None,
        sleep=None,
    ):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.extract_fn = extract_fn or fetch_resort_report
        self.intrawest_fn = intrawest_fn or fetch_intrawest_lifts
        self.fixture_path = fixture_path
        self.intrawest_fixture_path = intrawest_fixture_path

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        cfg = RESORT_SOURCES.get(market_id)
        if not cfg and not self.fixture_path:
            return [
                Observation(
                    signal_key="resort.terrain_open_pct",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    meta={"reason": "no_extractor_or_fixture"},
                )
            ]

        data: dict[str, Any] = {}
        src_val = cfg.get("html_url") if cfg else None
        src = str(src_val) if src_val is not None else None

        # --- Intrawest feed (Winter Park primary) --------------------------------
        lifts_raw: list[dict[str, Any]] | None = None
        if self.intrawest_fixture_path:
            lifts_raw = json.loads(
                Path(self.intrawest_fixture_path).read_text(encoding="utf-8")
            )
        elif cfg and cfg.get("feed_id") and not self.fixture_path:
            try:
                lifts_raw = self.intrawest_fn(int(cfg["feed_id"]))
            except Exception:  # noqa: BLE001 — fall through to HTML / fixture
                lifts_raw = None

        if lifts_raw is not None:
            feed_id = int(cfg.get("feed_id", WINTER_PARK_FEED_ID)) if cfg else WINTER_PARK_FEED_ID
            parsed = parse_intrawest_payload(lifts_raw, feed_id=feed_id)
            data.update(parsed)
            parsed_src = parsed.get("source_url")
            src = str(parsed_src) if parsed_src else src
            self.store.write_resort_snapshot(
                as_of=as_of,
                market_id=market_id,
                payload={"lifts": lifts_raw},
                source_url=src,
                lift_open=int(parsed.get("lifts_open", 0)),
                lift_total=int(parsed.get("lift_total", 0)),
                trail_open=int(parsed.get("trails_open", 0)),
                trail_total=int(parsed.get("trail_total", 0)),
            )

        # --- Legacy JSON fixture (tests / offline) --------------------------------
        if self.fixture_path and not lifts_raw:
            payload = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
            data.update(payload.get(market_id) or payload)

        # --- HTML fallback for base depth / ticket window -------------------------
        html_url_val = cfg.get("html_url") if cfg else None
        html_url = str(html_url_val) if html_url_val is not None else None
        if html_url and not self.fixture_path:
            try:
                html_data = self.extract_fn(html_url)
                for key in ("base_depth_in", "lift_ticket_window_usd"):
                    if html_data.get(key) is not None and data.get(key) is None:
                        data[key] = html_data[key]
                if data.get("terrain_open_pct") is None and html_data.get("terrain_open_pct") is not None:
                    data.update(
                        {
                            k: html_data[k]
                            for k in (
                                "terrain_open_pct",
                                "lifts_open",
                                "trails_open",
                            )
                            if html_data.get(k) is not None
                        }
                    )
            except Exception:  # noqa: BLE001
                pass

        if data.get("terrain_open_pct") is None:
            # Closed-for-season with zero open trails is valid terrain data (0%).
            if data.get("trail_total") and data.get("trails_open") is not None:
                data["terrain_open_pct"] = (
                    100.0 * float(data["trails_open"]) / float(data["trail_total"])
                )
            elif data.get("resort_open") == 0.0 and data.get("lift_total"):
                data["terrain_open_pct"] = 0.0

        if data.get("terrain_open_pct") is None:
            return [
                Observation(
                    signal_key="resort.terrain_open_pct",
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    provenance_url=src,
                    meta={"reason": "no_terrain_data"},
                )
            ]

        # Surface packed score heuristic from grooming coverage.
        groomed = data.get("trails_groomed_pct")
        if groomed is not None:
            data["surface_packed_score"] = min(1.0, float(groomed) / 100.0)

        mapping = {
            "terrain_open_pct": data.get("terrain_open_pct"),
            "lifts_open": data.get("lifts_open"),
            "trails_open": data.get("trails_open"),
            "base_depth_in": data.get("base_depth_in"),
            "lift_ticket_window_usd": data.get("lift_ticket_window_usd"),
            "lifts_on_hold": data.get("lifts_on_hold"),
            "trails_groomed_pct": data.get("trails_groomed_pct"),
            "resort_open": data.get("resort_open"),
            "surface_packed_score": data.get("surface_packed_score"),
        }
        obs: list[Observation] = []
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
