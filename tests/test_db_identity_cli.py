"""Demo/production DB identity and live-write CLI guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cli.main import build_parser, main
from src.db import (
    DB_KIND_DEMO,
    DB_KIND_PRODUCTION,
    connect,
    get_db_identity,
    init_db,
    mark_db_identity,
)
from src.pms import push_recommendations


def test_seed_sample_marks_demo_and_health_banners(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    db = tmp_path / "d.db"
    with pytest.raises(SystemExit) as seed:
        main(["--db", str(db), "seed-sample"])
    assert seed.value.code == 0
    with connect(db) as conn:
        assert get_db_identity(conn).kind == DB_KIND_DEMO
    capsys.readouterr()
    with pytest.raises(SystemExit) as health:
        main(["--db", str(db), "health"])
    assert health.value.code == 1
    out = capsys.readouterr().out
    assert "DEMO DATABASE" in out
    assert "Consecutive failed runs" in out
    assert "Grace state" in out


def test_seed_sample_refuses_production_without_force(tmp_path: Path):
    db = tmp_path / "d.db"
    init_db(db)
    with connect(db) as conn:
        mark_db_identity(conn, DB_KIND_PRODUCTION, "test")
        conn.commit()
    with pytest.raises(SystemExit) as seed:
        main(["--db", str(db), "seed-sample"])
    assert seed.value.code == 1
    with connect(db) as conn:
        assert get_db_identity(conn).kind == DB_KIND_PRODUCTION
    with pytest.raises(SystemExit) as forced:
        main(["--db", str(db), "seed-sample", "--force-demo"])
    assert forced.value.code == 0
    with connect(db) as conn:
        assert get_db_identity(conn).kind == DB_KIND_DEMO


def test_push_guesty_requires_confirm_flag(tmp_path: Path):
    db = tmp_path / "d.db"
    init_db(db)
    with pytest.raises(SystemExit) as exc:
        main([
            "--db", str(db), "push",
            "--from", "2026-12-05", "--to", "2026-12-05",
            "--adapter", "guesty",
        ])
    assert exc.value.code == 1


def test_push_guesty_refuses_unknown_identity_even_with_confirm(tmp_path: Path):
    db = tmp_path / "d.db"
    init_db(db)
    with pytest.raises(SystemExit) as exc:
        main([
            "--db", str(db), "push",
            "--from", "2026-12-05", "--to", "2026-12-05",
            "--adapter", "guesty", "--confirm-live-write",
        ])
    assert exc.value.code == 1


def test_push_guesty_refuses_when_no_locked_properties_in_db(tmp_path: Path):
    db = tmp_path / "d.db"
    init_db(db)
    with connect(db) as conn:
        mark_db_identity(conn, DB_KIND_PRODUCTION, "test")
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate)
               VALUES ('creekside_haven','Creekside',3,2,'[]',400,200,900)"""
        )
        conn.commit()
    with pytest.raises(SystemExit) as missing:
        main([
            "--db", str(db), "push",
            "--from", "2026-12-05", "--to", "2026-12-05",
            "--adapter", "guesty", "--confirm-live-write",
        ])
    assert missing.value.code == 1
    with pytest.raises(SystemExit) as extra:
        main([
            "--db", str(db), "push",
            "--from", "2026-12-05", "--to", "2026-12-05",
            "--adapter", "guesty", "--confirm-live-write",
            "--property", "creekside_haven",
        ])
    assert extra.value.code == 1


def test_push_recommendations_refuses_guesty_on_demo_db(tmp_path: Path):
    db = tmp_path / "d.db"
    init_db(db)

    class _Named:
        name = "guesty"

        def push_rate(self, *_a, **_k):
            raise AssertionError("Guesty adapter must not be called on a demo database")

    with connect(db) as conn:
        mark_db_identity(conn, DB_KIND_DEMO, "test")
        conn.commit()
        counts = push_recommendations(conn, [], _Named(), "handle")
    assert counts["attempted"] == 0
    assert counts["refused_db_kind"] == DB_KIND_DEMO


def test_hostaway_is_not_a_cli_push_choice():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["push", "--from", "2026-12-05", "--to", "2026-12-05",
                           "--adapter", "hostaway"])
