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


RATE_CARD = ROOT / "data" / "exports" / "rate_card.yaml"
# Policy season -> rate-card seasons it covers (policy peak_ski runs 15 Dec-31 Mar,
# so its caps also bind holiday week).
_CAP_SEASONS = {
    "peak_ski": ("peak_ski", "holiday"),
    "early_winter": ("early_winter",),
    "shoulder_spring": ("shoulder_spring",),
}


def check_rate_caps(rate_card: Path = RATE_CARD) -> tuple[list[str], str]:
    """A hard price cap below what the home really lists cuts real revenue.

    The peak caps were tuned in a simulator whose market was 2-3x too cheap
    (2026-10-14 audit). Compare every ``ceiling.property_season_ceiling`` cap
    with the 25th percentile of the home's real listed prices for the seasons
    it binds. Uses the local aggregate export (scripts/export_rate_card.py);
    skipped, not failed, where that file does not exist.
    """
    if not rate_card.exists():
        return [], f"rate-cap check SKIPPED: no {rate_card.relative_to(ROOT)} (run scripts/export_rate_card.py)"
    card = yaml.safe_load(rate_card.read_text(encoding="utf-8")) or {}
    homes = card.get("homes") or {}
    caps = (load_policy().get("ceiling") or {}).get("property_season_ceiling") or {}
    errors: list[str] = []
    checked = 0
    for prop_id, by_season in caps.items():
        seasons = (homes.get(prop_id) or {}).get("by_season") or {}
        for policy_season, cap in (by_season or {}).items():
            for card_season in _CAP_SEASONS.get(policy_season, (policy_season,)):
                p25 = (seasons.get(card_season) or {}).get("listed_p25")
                if p25 is None:
                    continue
                checked += 1
                if float(cap) < float(p25):
                    errors.append(
                        f"{prop_id} {policy_season} cap ${float(cap):,.0f} is below the real "
                        f"{card_season} listed p25 ${float(p25):,.0f}: it would cut real rates"
                    )
    return errors, f"rate-cap check: {checked} cap/season pairs vs {rate_card.relative_to(ROOT)}"


RUNTIME = Path("~/Library/Application Support/wp-price").expanduser()


def deployed_note(runtime: Path = RUNTIME) -> str:
    """Warn (never fail) when the daily jobs run code other than this checkout."""
    import subprocess

    marker = runtime / "DEPLOYED_SHA"
    if ROOT.resolve() == runtime.resolve():
        return "deploy check: running inside the runtime copy"
    if not marker.exists():
        return f"deploy check WARNING: no {marker}; the daily jobs' code version is unknown (scripts/deploy_runtime.sh)"
    deployed = marker.read_text(encoding="utf-8").split()[0]
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "deploy check: git unavailable"
    if deployed != head:
        return f"deploy check WARNING: daily jobs run {deployed[:8]}, this checkout is {head[:8]} (scripts/deploy_runtime.sh)"
    return f"deploy check: daily jobs run {head[:8]} (current)"


def main() -> int:
    print(deployed_note())
    rate_errors, rate_note = check_rate_caps()
    print(rate_note)
    errors = check_configs() + check_pipeline() + rate_errors
    if errors:
        print("PREFLIGHT FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PREFLIGHT OK: YAML invariants and ingest→features→ceiling→bookprob→compose contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
