"""Seasonal base anchor: an in-season reference cannot walk down to the floor."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from pathlib import Path

import pytest

from src import bookprob
from src.ceiling import compute_ceiling
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property


AS_OF = date(2027, 4, 20)
TARGET = date(2027, 4, 25)


def _shoulder_db(path: Path):
    """Summit Haus with ten April nights already sold at the floor."""
    init_db(path)
    conn = connect(path)
    conn.execute(
        """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
           base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
           VALUES ('summit_haus','Summit Haus',5,4,'[]',793,330,1800,'America/Denver','x')"""
    )
    for offset in range(10):
        stay = date(2027, 4, 2) + timedelta(days=offset)
        conn.execute(
            """INSERT INTO nightly_inventory
               (property_id, stay_date, listed_price, booked_price, status, day_of_week, booked_at)
               VALUES ('summit_haus', ?, 340, 340, 'booked', ?, '2027-03-15')""",
            (stay.isoformat(), stay.weekday()),
        )
    conn.execute(
        """INSERT INTO nightly_inventory
           (property_id, stay_date, listed_price, status, day_of_week)
           VALUES ('summit_haus', ?, 340, 'available', ?)""",
        (TARGET.isoformat(), TARGET.weekday()),
    )
    conn.commit()
    return conn


def _anchored(ref_ratio: float = 0.90, ceiling_ratio: float = 1.00) -> dict:
    policy = copy.deepcopy(load_policy())
    policy["seasonal_base_anchor"] = {
        "enabled": True,
        "price_ref_min_ratio": ref_ratio,
        "ceiling_min_ratio": ceiling_ratio,
    }
    return policy


def test_default_policy_leaves_the_anchor_off():
    assert not (load_policy().get("seasonal_base_anchor") or {}).get("enabled")


def test_anchor_lifts_a_floor_pinned_ceiling_and_reference(tmp_path: Path):
    with _shoulder_db(tmp_path / "a.db") as conn:
        feat = build_features_for_property(conn, "summit_haus", TARGET, TARGET, as_of=AS_OF)[0]
        base = feat.base_ceiling_rate * feat.season_multiplier
        assert feat.season == "shoulder_spring"

        plain_ceiling = compute_ceiling(conn, feat, load_policy(), as_of=AS_OF)
        plain_bp = bookprob.estimate(conn, feat, load_policy(), as_of=AS_OF)
        assert plain_ceiling.ceiling_price < base
        assert plain_bp.price_ref == pytest.approx(340)

        policy = _anchored()
        ceiling = compute_ceiling(conn, feat, policy, as_of=AS_OF)
        bp = bookprob.estimate(conn, feat, policy, as_of=AS_OF)
    assert ceiling.ceiling_price == pytest.approx(base)
    assert "+base_floor" in ceiling.method
    assert bp.price_ref == pytest.approx(0.90 * base)
    assert "(base_ref)" in bp.bucket


def test_property_season_cap_still_binds_over_the_anchor(tmp_path: Path):
    with _shoulder_db(tmp_path / "b.db") as conn:
        feat = build_features_for_property(conn, "summit_haus", TARGET, TARGET, as_of=AS_OF)[0]
        policy = _anchored()
        policy["ceiling"]["property_season_ceiling"] = {"summit_haus": {"shoulder_spring": 500}}
        ceiling = compute_ceiling(conn, feat, policy, as_of=AS_OF)
    assert ceiling.ceiling_price == pytest.approx(500)
