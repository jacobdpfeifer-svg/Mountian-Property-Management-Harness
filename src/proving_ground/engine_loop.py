"""Day-by-day production engine loop for the Proving Ground."""

from __future__ import annotations

import copy
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterator
from unittest.mock import patch

from src.compose import generate_recommendations
from src.config import load_policy
from src.pacing import take_snapshot
from src.signals.features.sqi import load_conditions
from proving_ground_exam.worlds.w1_calm import W1CalmWorld


@dataclass(frozen=True)
class EngineRunResult:
    run_id: str
    property_id: str
    decision_days: int
    recommendation_rows: int
    moat_off: bool


def _moat_off_conditions() -> dict[str, Any]:
    base = load_conditions()
    out = copy.deepcopy(base)
    out.setdefault("sqi", {})["enabled"] = False
    return out


@contextmanager
def _moat_off_patch() -> Iterator[None]:
    conditions = _moat_off_conditions()
    with patch("src.signals.features.sqi.load_conditions", return_value=conditions):
        yield


def run_engine_season(
    conn: sqlite3.Connection,
    world: W1CalmWorld,
    *,
    level: int,
    moat_off: bool = False,
    run_id: str | None = None,
    decision_step_days: int = 7,
) -> EngineRunResult:
    """Run the real pricing pipeline once per simulated decision day.

    ``decision_step_days`` defaults to weekly cadence for Phase 0 wall-clock time.
    Daily stepping remains the Phase B target once run caching lands.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    policy = load_policy()
    property_id = world.property_id
    decision_days = 0
    step = max(1, int(decision_step_days))

    ctx = _moat_off_patch() if moat_off else _nullcontext()
    with ctx:
        d = world.season_start
        while d <= world.season_end:
            world.advance(conn, d, level=level)
            take_snapshot(conn, as_of=d)
            generate_recommendations(
                conn,
                d,
                world.season_end,
                property_ids=[property_id],
                policy=policy,
                persist=True,
                allow_past=True,
                as_of=d,
                run_id=run_id,
            )
            decision_days += 1
            d += timedelta(days=step)

    rows = conn.execute(
        """
        SELECT COUNT(*) AS c FROM price_recommendations
        WHERE run_id = ? AND property_id = ?
        """,
        (run_id, property_id),
    ).fetchone()
    return EngineRunResult(
        run_id=run_id,
        property_id=property_id,
        decision_days=decision_days,
        recommendation_rows=int(rows["c"] if rows else 0),
        moat_off=moat_off,
    )


def read_engine_prices(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    property_id: str,
) -> dict[date, float]:
    out: dict[date, float] = {}
    rows = conn.execute(
        """
        SELECT stay_date, recommended_price FROM price_recommendations
        WHERE run_id = ? AND property_id = ?
        """,
        (run_id, property_id),
    ).fetchall()
    for row in rows:
        out[date.fromisoformat(str(row["stay_date"]))] = float(row["recommended_price"])
    return out


def read_engine_probs(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    property_id: str,
) -> dict[date, float]:
    out: dict[date, float] = {}
    rows = conn.execute(
        """
        SELECT stay_date, expected_book_prob FROM price_recommendations
        WHERE run_id = ? AND property_id = ?
        """,
        (run_id, property_id),
    ).fetchall()
    for row in rows:
        if row["expected_book_prob"] is not None:
            out[date.fromisoformat(str(row["stay_date"]))] = float(row["expected_book_prob"])
    return out


class _nullcontext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None
