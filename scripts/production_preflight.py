#!/usr/bin/env python3
"""Deterministic production preflight for the Mont Luxe pricing pipeline.

This intentionally checks executable handoffs instead of duplicating business
logic: ingest -> features -> ceiling -> booking probability -> compose, plus
YAML parsing and safety-bound invariants.
"""

from __future__ import annotations

import tempfile
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bookprob import estimate
from src.ceiling import compute_ceiling
from src.compose import recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property
from src.ingest import CsvIngestAdapter


def check_configs() -> list[str]:
    errors: list[str] = []
    for path in sorted((ROOT / "config").rglob("*.yaml")):
        with path.open() as fh:
            yaml.safe_load(fh)
    policy = load_policy()
    guard = policy["guardrails"]
    if guard["max_increase_pct"] <= 0 or guard["max_decrease_pct"] <= 0:
        errors.append("move caps must be positive")
    if guard["sanity_min_ratio_to_anchor"] <= 0 or guard["sanity_min_ratio_to_anchor"] > 1:
        errors.append("sanity_min_ratio_to_anchor must be in (0, 1]")
    if policy["global"]["min_price"] > policy["global"]["max_price"]:
        errors.append("global min_price exceeds max_price")
    if policy["data_health"]["demotion_grace_runs"] < 1:
        errors.append("demotion_grace_runs must be at least 1")
    lookback = float(policy["ceiling"].get("history_lookback_years", 0))
    if not 1 <= lookback <= 10:
        errors.append("history_lookback_years must be between 1 and 10")
    if int(policy["ceiling"].get("yoy_calendar_window_days", -1)) < 0:
        errors.append("yoy_calendar_window_days must be >= 0")
    if policy["ceiling"].get("allow_cross_season_fallback"):
        errors.append("allow_cross_season_fallback must stay false in default policy")
    for name, season in policy["seasons"].items():
        if season["base_multiplier"] <= 0:
            errors.append(f"season {name} has non-positive multiplier")
    return errors


def check_pipeline() -> list[str]:
    errors: list[str] = []
    sample = ROOT / "data" / "sample"
    policy = load_policy()
    with tempfile.TemporaryDirectory(prefix="wp-price-preflight-") as tmp:
        db_path = Path(tmp) / "preflight.db"
        init_db(db_path)
        with connect(db_path) as conn:
            CsvIngestAdapter(
                properties_csv=sample / "properties.csv",
                inventory_csv=sample / "nightly_inventory.csv",
                comps_csv=sample / "comps.csv",
                demand_csv=sample / "demand_signals.csv",
                inquiries_csv=sample / "booking_inquiries.csv",
            ).load_all(conn)
            features = build_features_for_property(
                conn, "aspen_glow", date(2026, 12, 1), date(2026, 12, 1), policy=policy
            )
            if not features:
                return ["features emitted no representative night"]
            feat = features[0]
            ceiling = compute_ceiling(conn, feat, policy)
            if ceiling.ceiling_price < ceiling.floor_price:
                errors.append("ceiling emitted below floor")
            bp = estimate(conn, feat, policy)
            if not 0 <= bp.prob_at(feat.listed_price or ceiling.floor_price) <= 1:
                errors.append("bookprob emitted an out-of-range probability")
            rec = recommend_night(conn, feat, policy=policy)
            if rec is None:
                errors.append("compose emitted no recommendation for available night")
            else:
                if rec.expected_book_prob is None or rec.expected_revpan is None:
                    errors.append("compose dropped booking probability or expected RevPAN")
                if rec.floor_price > rec.recommended_price:
                    errors.append("compose emitted recommendation below floor")
    return errors


def main() -> int:
    errors = check_configs() + check_pipeline()
    if errors:
        print("PREFLIGHT FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PREFLIGHT OK: YAML invariants and ingest→features→ceiling→bookprob→compose contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
