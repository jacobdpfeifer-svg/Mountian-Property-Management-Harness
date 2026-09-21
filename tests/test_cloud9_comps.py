"""Cloud 9 market tagging and scraper-driven comp membership."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.config import load_markets, load_portfolio_config
from src.db import connect, init_db
from src.ingest import CsvIngestAdapter
from src.scrape import run_scrape
from src.scrape.providers import FixtureProvider

ROOT = Path(__file__).resolve().parents[1]
CLOUD9_COMPS = ROOT / "data" / "cloud9" / "comps.csv"
START = date(2026, 12, 18)


def test_cloud9_shares_grand_home_market_with_twins():
    portfolio = load_portfolio_config()
    markets = {m["market_id"]: m for m in load_markets()["markets"]}
    home = markets["grand_home"]
    assert home["name"] == "Winter Park / Fraser / Tabernash"
    props = portfolio["properties"]
    for pid in ("summit_haus", "overlook_ridge", "cloud_9"):
        assert props[pid]["market_id"] == "grand_home"
    assert props["cloud_9"]["town"] == "Fraser"


def test_cloud9_airbnb_comps_refresh_on_same_scrape_path(tmp_path: Path):
    path = tmp_path / "c9.db"
    init_db(path)
    fixture = tmp_path / "sweep.json"
    fixture.write_text(
        '{"sweeps": {"2026-12-18": ['
        '{"room_id": "897819634480326640", "nightly_price": 1360, "name": "Ranch Creek",'
        ' "bedrooms": 5, "sleeps": 18},'
        '{"room_id": "28918989", "nightly_price": 814, "name": "Family Friendly",'
        ' "bedrooms": 6, "sleeps": 16}'
        "]}}",
        encoding="utf-8",
    )
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id, name, bedrooms, bathrooms, amenities,
               base_ceiling_rate, min_floor_rate, max_ceiling_rate, timezone, owner_id, market_id)
               VALUES ('cloud_9','Cloud 9',6,4.5,'[]',1100,400,2000,'America/Denver','cloud9','grand_home')"""
        )
        CsvIngestAdapter(comps_csv=CLOUD9_COMPS).load_all(conn)
        members = {
            r["comp_id"]
            for r in conn.execute(
                "SELECT comp_id FROM comp_set_members WHERE property_id='cloud_9'"
            )
        }
        assert "comp_ranch_creek" in members
        assert "comp_deer" in members  # direct-book stays in the set
        policy = {
            "scrape": {
                "window_nights": 2,
                "validation": {
                    "min_listings_per_sweep": 1,
                    "min_parse_rate": 0.5,
                    "max_identical_share": 1.0,
                    "min_plausible_price": 20,
                    "max_plausible_price": 20000,
                    "max_change_ratio": 5.0,
                    "min_window_success_rate": 0.5,
                    "min_comp_match_rate": 0.1,
                },
            }
        }
        rep = run_scrape(
            conn,
            FixtureProvider(fixture),
            policy,
            horizon_days=2,
            start=START,
            fetch_calendars=False,
        )
        assert rep.status == "ok"
        priced = {
            r["comp_id"]
            for r in conn.execute(
                "SELECT DISTINCT comp_id FROM comp_snapshots "
                "WHERE scrape_status='ok' AND listed_price IS NOT NULL"
            )
        }
        assert "comp_ranch_creek" in priced
        assert "comp_family_friendly" in priced
        # Direct-book members have no airbnb_room_id, so the sweep does not index them.
        deer_snaps = conn.execute(
            "SELECT COUNT(*) c FROM comp_snapshots WHERE comp_id='comp_deer'"
        ).fetchone()["c"]
        assert deer_snaps == 0
