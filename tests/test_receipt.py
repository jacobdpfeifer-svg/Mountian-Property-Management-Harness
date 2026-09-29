"""Run receipt renders stored facts and does not invent reasons."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.cli.main import main
from src.db import connect, init_db
from src.ingest import upsert_property
from src.receipt.render import write_receipt


def _property(conn, pid: str) -> None:
    upsert_property(conn, {
        "property_id": pid,
        "name": pid,
        "bedrooms": 4,
        "bathrooms": 3,
        "amenities": "[]",
        "base_ceiling_rate": 3000,
        "min_floor_rate": 800,
        "max_ceiling_rate": 4000,
        "luxury_tier": "luxury",
        "target_alos": 3,
        "timezone": "America/Denver",
    })


def _night(conn, **kwargs) -> None:
    reasons = kwargs.pop("reasons")
    conn.execute(
        """
        INSERT INTO price_recommendations (
            run_id, property_id, stay_date, recommended_price, ceiling_price,
            floor_price, listed_price_at_run, ceiling_confidence, autonomy_level,
            guardrail_action, reasons, rule_version, model_version, inputs_hash,
            status, weak_ceiling, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kwargs["run_id"], kwargs["property_id"], kwargs["stay_date"].isoformat(),
            kwargs["price"], kwargs["ceiling"], kwargs["floor"], kwargs["listed"],
            0.4, kwargs.get("autonomy", "suggest"), kwargs.get("guardrail"),
            json.dumps(reasons), "rules-test", "model-test", kwargs.get("inputs_hash", "abc123"),
            kwargs.get("status", "suggested"), int(kwargs.get("weak", False)),
            "2026-09-29 07:08:00",
        ),
    )


def test_receipt_is_stable_and_uses_only_stored_sentences(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MONTLUXE_MEMORY_ROOT", str(tmp_path / "memory"))
    db = tmp_path / "wp.db"
    init_db(db, seed_markets=False)
    with connect(db) as conn:
        for pid in ("summit_haus", "overlook_ridge", "cloud_9"):
            _property(conn, pid)
        stored = "Christmas demand supports a higher rate."
        thin = "The top of the range leans on seasonal history; comparable evidence is thin."
        _night(
            conn, run_id="runfixed", property_id="summit_haus", stay_date=date(2026, 12, 25),
            price=2845, ceiling=3000, floor=1800, listed=2600,
            reasons=[
                {"code": "event_boost", "message": stored, "contribution": 245},
                {"code": "thin_history", "message": thin, "contribution": 40},
                {"code": "snow_demand", "message": ""},
            ],
        )
        _night(
            conn, run_id="runfixed", property_id="overlook_ridge", stay_date=date(2026, 12, 25),
            price=2600, ceiling=3000, floor=1800, listed=2600,
            reasons=[{"code": "thin_history", "message": thin, "contribution": 0}],
        )
        _night(
            conn, run_id="runfixed", property_id="cloud_9", stay_date=date(2026, 1, 8),
            price=1265, ceiling=1400, floor=900, listed=1260, weak=True,
            guardrail="clamped_decrease",
            reasons=[{
                "code": "guardrail",
                "message": "The suggested decrease was capped so it stays within the allowed move from your current listing.",
                "contribution": -15,
            }],
        )
        conn.execute(
            """
            INSERT INTO data_health_runs (
                run_id, as_of, comp_coverage, granted_level, failures
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "runfixed", "2026-09-29 06:59:00", 0.42, "suggest",
                json.dumps(["comp coverage 42% below 60%"]),
            ),
        )
        conn.commit()

    first = write_receipt(db, "runfixed")
    second = write_receipt(db, "runfixed")
    text = first.read_text(encoding="utf-8")
    assert text == second.read_text(encoding="utf-8")
    assert stored in text
    assert thin in text
    assert text.index(stored) < text.index(thin)
    assert "snow demand" not in text.lower()
    assert "comp coverage 42% below 60%" in text
    assert "weak ceiling" in text
    assert "clamped_decrease" in text
    assert "Suggestions only" in text
    assert "nothing was pushed" in text
    assert "Twin check" in text
    assert "312 Northwoods" in text
    assert "300 Northwoods" in text
    assert "No decision needs you" not in text
    assert first.parent.name == "2026-09-29"
    assert "Mobile Documents" not in str(first)


def test_quiet_run_says_no_decision(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MONTLUXE_MEMORY_ROOT", str(tmp_path / "memory"))
    db = tmp_path / "wp.db"
    init_db(db, seed_markets=False)
    with connect(db) as conn:
        _property(conn, "cloud_9")
        _night(
            conn, run_id="quiet", property_id="cloud_9", stay_date=date(2026, 1, 15),
            price=1000, ceiling=1400, floor=800, listed=1000,
            reasons=[{"code": "base_compose", "message": "Seasonal level held.", "contribution": 0}],
        )
        conn.execute(
            "INSERT INTO data_health_runs (run_id, as_of, granted_level, failures) VALUES (?, ?, ?, ?)",
            ("quiet", "2026-09-29 07:00:00", "suggest", "[]"),
        )
        conn.commit()
    text = write_receipt(db, "quiet").read_text(encoding="utf-8")
    assert "No decision needs you" in text


def test_receipt_cli(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("MONTLUXE_MEMORY_ROOT", str(tmp_path / "memory"))
    db = tmp_path / "wp.db"
    init_db(db, seed_markets=False)
    with connect(db) as conn:
        _property(conn, "cloud_9")
        _night(
            conn, run_id="cli", property_id="cloud_9", stay_date=date(2026, 2, 1),
            price=1100, ceiling=1500, floor=700, listed=1000,
            reasons=[{"code": "event_boost", "message": "A stored reason.", "contribution": 100}],
        )
        conn.commit()
    with pytest.raises(SystemExit) as exc:
        main(["--db", str(db), "receipt", "--run-id", "cli"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "cli.html" in out
    assert "A stored reason." in Path(out.strip()).read_text(encoding="utf-8")
