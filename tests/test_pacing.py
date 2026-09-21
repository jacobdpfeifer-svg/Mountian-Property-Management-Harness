"""Pacing snapshot crash-safety and gap detection."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.cli.main import main
from src.db import connect, init_db
from src.pacing import take_snapshot, verify_snapshots


def _seed(conn, *, created_at: str = "2026-09-01") -> None:
    conn.execute(
        """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
           base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id,created_at)
           VALUES ('summit_haus','Summit Haus',5,5.5,'[]',900,400,2500,'America/Denver','g1',?)""",
        (created_at,),
    )
    conn.execute(
        """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
           base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id,created_at)
           VALUES ('overlook_ridge','Overlook Ridge',5,5.5,'[]',900,400,2500,'America/Denver','g2',?)""",
        (created_at,),
    )
    conn.execute(
        """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
           base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id,created_at)
           VALUES ('cloud_9','Cloud 9',5,4.5,'[]',800,350,2200,'America/Denver','g3',?)""",
        (created_at,),
    )
    today = date.today()
    for pid in ("summit_haus", "overlook_ridge", "cloud_9"):
        for i in range(5):
            stay = today + timedelta(days=i)
            conn.execute(
                """INSERT INTO nightly_inventory
                   (property_id, stay_date, listed_price, status, day_of_week)
                   VALUES (?, ?, 900, 'available', ?)""",
                (pid, stay.isoformat(), stay.weekday()),
            )
    conn.commit()


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "pacing.db"
    init_db(path)
    with connect(path) as conn:
        _seed(conn)
    return path


def test_take_snapshot_commits_once_and_covers_all_properties(db: Path):
    with connect(db) as conn:
        result = take_snapshot(conn, as_of=date.today())
        assert result["status"] == "ok"
        assert result["nights_captured"] == 15
        assert set(result["properties_captured"]) == {"summit_haus", "overlook_ridge", "cloud_9"}
        n = conn.execute("SELECT COUNT(*) c FROM pacing_snapshots").fetchone()["c"]
    assert n == 15


def test_verify_ok_when_every_day_is_present(db: Path):
    today = date.today()
    with connect(db) as conn:
        take_snapshot(conn, as_of=today)
        report = verify_snapshots(conn, as_of=today, since=today)
    assert report["status"] == "ok"
    assert report["gaps"] == []
    assert report["properties"] == 3


def test_verify_detects_deliberate_gap(db: Path):
    today = date.today()
    yesterday = today - timedelta(days=1)
    with connect(db) as conn:
        take_snapshot(conn, as_of=yesterday)
        take_snapshot(conn, as_of=today)
        conn.execute(
            "DELETE FROM pacing_snapshots WHERE as_of = ? AND property_id = 'cloud_9'",
            (yesterday.isoformat(),),
        )
        conn.commit()
        report = verify_snapshots(conn, as_of=today, since=yesterday)
    assert report["status"] == "degraded"
    assert report["gaps"] == [{"property_id": "cloud_9", "as_of": yesterday.isoformat()}]


def test_cli_verify_exits_nonzero_on_gap(db: Path, capsys):
    today = date.today().isoformat()
    with pytest.raises(SystemExit) as exited:
        main(["--db", str(db), "snapshot", "--verify", "--since", today])
    assert exited.value.code == 1
    out = capsys.readouterr().out
    assert '"status": "degraded"' in out
    assert "cloud_9" in out


def test_cli_verify_exits_zero_when_complete(db: Path):
    with connect(db) as conn:
        take_snapshot(conn, as_of=date.today())
    with pytest.raises(SystemExit) as exited:
        main(["--db", str(db), "snapshot", "--verify", "--since", date.today().isoformat()])
    assert exited.value.code == 0


def test_cli_snapshot_exits_nonzero_when_nothing_captured(tmp_path: Path):
    path = tmp_path / "empty.db"
    init_db(path)
    with pytest.raises(SystemExit) as exited:
        main(["--db", str(path), "snapshot"])
    assert exited.value.code == 1
