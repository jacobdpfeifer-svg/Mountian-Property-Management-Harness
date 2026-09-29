from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.cli.main import main as cli_main
from src.compose import generate_recommendations
from src.config import load_policy
from src.db import connect, init_db
from src.eval.shadow import GuestyWriteForbidden, record_shadow_day
from src.ingest import CsvIngestAdapter

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"


def _seed(path: Path) -> None:
    init_db(path)
    with connect(path) as conn:
        CsvIngestAdapter(
            properties_csv=SAMPLE / "properties.csv",
            inventory_csv=SAMPLE / "nightly_inventory.csv",
            comps_csv=SAMPLE / "comps.csv",
            demand_csv=SAMPLE / "demand_signals.csv",
            inquiries_csv=SAMPLE / "booking_inquiries.csv",
        ).load_all(conn)


def test_shadow_record_writes_local_rows_without_guesty(tmp_path: Path):
    db = tmp_path / "shadow.db"
    _seed(db)
    policy = load_policy()
    with connect(db) as conn:
        generate_recommendations(
            conn, date(2026, 12, 1), date(2026, 12, 7),
            property_ids=["aspen_glow"], policy=policy,
        )
        n = record_shadow_day(conn, as_of=date(2026, 12, 1), property_id="aspen_glow")
        assert n > 0
        row = conn.execute(
            "SELECT recommended_price, guesty_listed_price, season FROM shadow_daily "
            "WHERE property_id='aspen_glow' LIMIT 1"
        ).fetchone()
        assert row["season"]
        writes = conn.execute(
            "SELECT COUNT(*) c FROM rate_changes WHERE result='applied'"
        ).fetchone()["c"]
        assert writes == 0


def test_shadow_record_cli_and_refuses_guesty_writes(tmp_path: Path, capsys):
    db = tmp_path / "shadow.db"
    _seed(db)
    policy = load_policy()
    with connect(db) as conn:
        generate_recommendations(
            conn, date(2026, 12, 1), date(2026, 12, 3),
            property_ids=["aspen_glow"], policy=policy,
        )
    with pytest.raises(SystemExit) as rec:
        cli_main([
            "--db", str(db), "shadow-record",
            "--property", "aspen_glow",
            "--as-of", "2026-12-01",
        ])
    assert rec.value.code == 0
    out = capsys.readouterr().out
    assert "Guesty writes=0" in out

    with connect(db) as conn:
        conn.execute(
            """INSERT INTO rate_changes
               (property_id, stay_date, old_price, new_price, actor, autonomy_level, result)
               VALUES ('aspen_glow','2026-12-01',100,110,'guesty','suggest','applied')"""
        )
        conn.commit()
        with pytest.raises(GuestyWriteForbidden):
            record_shadow_day(conn, as_of=date(2026, 12, 1), property_id="aspen_glow")
