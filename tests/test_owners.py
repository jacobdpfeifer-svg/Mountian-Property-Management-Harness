"""Owner scoping — properties.owner_id and --owner filters."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.db import connect, init_db, resolve_property_ids
from src.eval import compute_revpan, portfolio_reports
from src.ingest import upsert_inventory, upsert_property


def _seed_two_owners(conn) -> None:
    upsert_property(conn, {
        "property_id": "summit_haus",
        "name": "Summit Haus",
        "bedrooms": 5,
        "bathrooms": 5.5,
        "amenities": [],
        "base_ceiling_rate": 1600,
        "min_floor_rate": 300,
        "max_ceiling_rate": 4000,
        "owner_id": "northwoods",
    })
    upsert_property(conn, {
        "property_id": "overlook_ridge",
        "name": "Overlook Ridge",
        "bedrooms": 5,
        "bathrooms": 5.5,
        "amenities": [],
        "base_ceiling_rate": 1600,
        "min_floor_rate": 300,
        "max_ceiling_rate": 4000,
        "owner_id": "northwoods",
    })
    upsert_property(conn, {
        "property_id": "cloud_9",
        "name": "Cloud 9",
        "bedrooms": 6,
        "bathrooms": 4.5,
        "amenities": [],
        "base_ceiling_rate": 1100,
        "min_floor_rate": 400,
        "max_ceiling_rate": 2000,
        "owner_id": "cloud9",
    })
    for pid, price in (("summit_haus", 500), ("overlook_ridge", 600), ("cloud_9", 900)):
        upsert_inventory(conn, {
            "property_id": pid,
            "stay_date": "2026-12-20",
            "listed_price": price,
            "booked_price": price,
            "status": "booked",
        })
    conn.commit()


def test_owner_id_patch_and_backfill(tmp_path: Path):
    path = tmp_path / "owners.db"
    init_db(path)
    with connect(path) as conn:
        _seed_two_owners(conn)
        # Clear then reconnect so _backfill_owner_ids runs.
        conn.execute("UPDATE properties SET owner_id = NULL")
        conn.commit()
    with connect(path) as conn:
        rows = {
            r["property_id"]: r["owner_id"]
            for r in conn.execute("SELECT property_id, owner_id FROM properties")
        }
    assert rows["summit_haus"] == "northwoods"
    assert rows["overlook_ridge"] == "northwoods"
    assert rows["cloud_9"] == "cloud9"


def test_report_does_not_leak_across_owners(tmp_path: Path):
    path = tmp_path / "owners.db"
    init_db(path)
    with connect(path) as conn:
        _seed_two_owners(conn)
        start, end = date(2026, 12, 20), date(2026, 12, 20)
        nw = portfolio_reports(conn, start, end, owner_id="northwoods")
        c9 = portfolio_reports(conn, start, end, owner_id="cloud9")

    nw_ids = {r.property_id for r in nw if r.property_id}
    c9_ids = {r.property_id for r in c9 if r.property_id}
    assert nw_ids == {"summit_haus", "overlook_ridge"}
    assert c9_ids == {"cloud_9"}
    assert "cloud_9" not in nw_ids
    assert "summit_haus" not in c9_ids
    assert "overlook_ridge" not in c9_ids

    nw_all = [r for r in nw if r.owner_id == "northwoods"][0]
    c9_all = [r for r in c9 if r.owner_id == "cloud9"][0]
    assert nw_all.booked_nights == 2
    assert nw_all.revenue == 1100
    assert c9_all.booked_nights == 1
    assert c9_all.revenue == 900


def test_resolve_property_ids_rejects_cross_owner(tmp_path: Path):
    path = tmp_path / "owners.db"
    init_db(path)
    with connect(path) as conn:
        _seed_two_owners(conn)
        assert resolve_property_ids(conn, owner_id="cloud9") == ["cloud_9"]
        try:
            resolve_property_ids(
                conn, property_ids=["cloud_9"], owner_id="northwoods"
            )
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "cloud_9" in str(exc)


def test_unscoped_resolve_omits_extra_listings(tmp_path: Path):
    path = tmp_path / "owners.db"
    init_db(path)
    with connect(path) as conn:
        _seed_two_owners(conn)
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate)
               VALUES ('creekside_haven','Creekside',3,2,'[]',400,200,900)"""
        )
        conn.commit()
        scoped = resolve_property_ids(conn)
    assert scoped == ["summit_haus", "overlook_ridge", "cloud_9"]
    assert "creekside_haven" not in scoped

