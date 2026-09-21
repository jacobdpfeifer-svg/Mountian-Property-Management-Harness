"""Guesty sync + small-data safety tests.

The regression that motivates most of this file: on the live tenant, last Christmas
averaged an earlier seasonal level and this Christmas averages a higher seasonal level (realised $a much higher realized price). A model
fitted on that history wanted a -35% cut on the strongest nights of the year — i.e.
to restore last season's underpricing. Everything below pins the behaviour that
stops a thin-history model from overruling the operator.
"""

from __future__ import annotations

import ast
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
import pytest
import requests

from src.ceiling import compute_ceiling, demand_tier, seasonal_anchor
from src.compose import recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property
from src.pms.guesty import GuestyClient, GuestyListing, parse_guesty_date
from src.pms.sync import SyncReport, _floor_and_ceiling, recalibrate_bounds


def _listing(**kw) -> GuestyListing:
    base = dict(listing_id="abc123", nickname="Test Haus", title="t", bedrooms=5,
                bathrooms=5.5, accommodates=16, base_price=420.0,
                weekend_base_price=618.0, cleaning_fee=650.0, min_nights=2,
                address="1 Test St", city="Winter Park", lat=39.89, lng=-105.75,
                timezone="America/Denver", active=True, amenities=[])
    base.update(kw)
    return GuestyListing(**base)


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "g.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('test_haus','Test Haus',5,5.5,'[]',711,252,1854,'America/Denver','abc123')"""
        )
        conn.commit()
    return path


# ------------------------------------------------------------------ identity

def test_property_id_is_a_stable_slug():
    assert _listing(nickname="Summit Haus").property_id == "summit_haus"
    assert _listing(nickname="Cloud 9").property_id == "cloud_9"
    assert _listing(nickname="Café / Lodge!").property_id == "cafe_lodge"
    assert _listing(nickname="   ").property_id == "abc123"  # falls back to listing id
    assert _listing(
        listing_id="6a8e355230f5b5007c81df4b", nickname="Cloud 9 Chalet"
    ).property_id == "cloud_9"


def test_parse_guesty_date_handles_iso_timestamps():
    assert parse_guesty_date("2026-12-27T00:00:00.000Z") == date(2026, 12, 27)
    assert parse_guesty_date("2026-12-27") == date(2026, 12, 27)
    assert parse_guesty_date(None) is None
    assert parse_guesty_date("nonsense") is None


# --------------------------------------------------------------------- bounds

def test_base_price_seed_is_only_provisional():
    """Guesty basePrice is a STARTING rate, not a ceiling. The seed must be treated as
    provisional or a $420 base caps a property that sells at $a much higher realized price."""
    floor, base_ceiling, _ = _floor_and_ceiling(_listing())
    assert base_ceiling < 800, "seed is intentionally low; recalibrate_bounds must fix it"
    assert floor < base_ceiling


def test_recalibrate_bounds_uses_observed_prices(db: Path):
    """REGRESSION: seeding the ceiling from Guesty's basePrice produced an $818 anchor
    on nights the operator lists at $2,700, driving a -70% Christmas recommendation."""
    with connect(db) as conn:
        d = date(2026, 12, 1)
        for i in range(60):
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,?,'available',?)",
                ((d + timedelta(days=i)).isoformat(), 2600 + i * 5, (d + timedelta(days=i)).weekday()),
            )
        conn.commit()
        report = SyncReport()
        recalibrate_bounds(conn, report)
        row = conn.execute(
            "SELECT min_floor_rate, base_ceiling_rate, max_ceiling_rate FROM properties"
        ).fetchone()
    assert row["base_ceiling_rate"] > 2500, "ceiling must follow observed prices, not basePrice"
    assert row["max_ceiling_rate"] > row["base_ceiling_rate"]
    assert row["min_floor_rate"] > 1000


# ---------------------------------------------------------------- demand tiers

def test_demand_tier_separates_holiday_from_ordinary_peak():
    policy = load_policy()
    assert demand_tier(0.95, policy) == "high"    # Christmas
    assert demand_tier(0.55, policy) == "mid"
    assert demand_tier(0.20, policy) == "low"     # ordinary January midweek


def test_anchor_prefers_same_demand_tier(db: Path):
    """peak_ski spans 15 Dec - 31 Mar. Without tier matching, a Christmas night anchors
    to a mid-January price."""
    policy = load_policy()
    with connect(db) as conn:
        # cheap ordinary peak nights (Jan) + expensive holiday nights (late Dec)
        for i in range(40):
            d = date(2027, 1, 10) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,700,'available',?)", (d.isoformat(), d.weekday()))
        for i in range(14):
            d = date(2026, 12, 21) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", date(2026, 12, 23),
                                            date(2026, 12, 23), policy=policy)
        anchor = seasonal_anchor(feats[0], policy, conn)
    assert feats[0].demand_strength >= 0.8, "Christmas should read as high demand"
    assert anchor > 2000, f"holiday anchored to ordinary-peak price: ${anchor:.0f}"


# ----------------------------------------------------------------- deference

def test_low_confidence_defers_to_the_operators_price(db: Path):
    """THE headline safety property. With thin history the model must nudge the
    incumbent price, never reverse it."""
    policy = load_policy()
    with connect(db) as conn:
        # A repriced holiday: cheap last year, expensive this year, nothing realised.
        for i in range(20):
            d = date(2025, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,480,'available',?)", (d.isoformat(), d.weekday()))
        for i in range(16):
            d = date(2026, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", date(2026, 12, 23),
                                            date(2026, 12, 23), policy=policy)
        rec = recommend_night(conn, feats[0], policy=policy)
    assert rec is not None
    drop = (rec.listed_price_at_run - rec.recommended_price) / rec.listed_price_at_run
    assert drop < 0.20, f"model overruled the operator by {drop:.0%} on thin evidence"
    assert rec.ceiling_confidence < 0.80


def test_deference_does_not_fire_at_high_confidence(db: Path):
    """Deference must not blunt a well-evidenced recommendation."""
    policy = load_policy()
    with connect(db) as conn:
        d = date(2026, 9, 20)
        for i in range(120):
            day = d + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,"
                "booked_price,status,day_of_week) VALUES ('test_haus',?,?,?,'booked',?)",
                (day.isoformat(), 500, 500, day.weekday()))
        target = date(2027, 10, 6)
        conn.execute(
            "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
            " VALUES ('test_haus',?,500,'available',?)", (target.isoformat(), target.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", target, target, policy=policy)
        ceiling = compute_ceiling(conn, feats[0], policy)
    assert ceiling.confidence >= 0.80
    assert "season" in ceiling.method


def test_peak_nights_never_auto_push(db: Path):
    """Christmas must escalate regardless of what the model wants."""
    policy = load_policy()
    with connect(db) as conn:
        d = date(2026, 12, 23)
        conn.execute(
            "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
            " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", d, d, policy=policy)
        rec = recommend_night(conn, feats[0], policy=policy)
    assert rec.status == "blocked"
    assert rec.autonomy_level == "escalate"
    assert rec.guardrail_action == "peak_blackout"


# ---------------------------------------------------------- write-path safety

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _py_files():
    return [p for p in SRC.rglob("*.py") if p.is_file()]


def test_set_rate_is_unreachable_without_push_recommendations():
    """REGRESSION: the only .set_rate( call in production is GuestyAdapter.push_rate,
    which is only invoked from push_recommendations after generate_recommendations
    (and therefore apply_guardrails). A 'quick fix' CLI write must fail this test.
    """
    call_sites: list[tuple[str, int, str]] = []
    for path in _py_files():
        rel = str(path.relative_to(ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name == "set_rate":
                line = path.read_text(encoding="utf-8").splitlines()[node.lineno - 1].strip()
                call_sites.append((rel, node.lineno, line))
    assert len(call_sites) == 1, f"unexpected set_rate callers: {call_sites}"
    assert call_sites[0][0] == "src/pms/__init__.py"
    assert "self.client.set_rate" in call_sites[0][2]

    push_rate_callers: list[tuple[str, int]] = []
    for path in _py_files():
        rel = str(path.relative_to(ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None
            )
            if name != "push_rate":
                continue
            push_rate_callers.append((rel, node.lineno))
    assert len(push_rate_callers) == 1, (
        f"unexpected push_rate callers (bypass of apply_guardrails): {push_rate_callers}"
    )
    assert push_rate_callers[0][0] == "src/pms/__init__.py"

    for rel in ("src/cli/main.py", "src/pms/sync.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert ".set_rate(" not in text
        assert "set_rate(" not in text


class _Resp:
    def __init__(self, status: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code}", response=self)
            raise err

    def json(self):
        return self._payload


def _client() -> GuestyClient:
    c = GuestyClient(client_id="id", client_secret="secret", use_token_cache=False)
    c._token = "tok"
    c._expires_at = time.time() + 10_000
    return c


def test_set_rate_retries_transient_failures_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    client = _client()
    sleeps: list[float] = []
    monkeypatch.setattr("src.pms.guesty.time.sleep", lambda s: sleeps.append(s))
    attempts = {"n": 0}

    def fake_put(*_a, **_k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise requests.Timeout("timed out")
        if attempts["n"] == 2:
            return _Resp(503)
        return _Resp(200, headers={"x-request-id": "abc"})

    monkeypatch.setattr("requests.put", fake_put)
    ok, err = client.set_rate("listing1", date(2026, 12, 10), 555.0)
    assert ok is True
    assert attempts["n"] == 3
    assert sleeps  # backoff between retries
    assert err == "request_id=abc"


def test_set_rate_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch):
    client = _client()
    monkeypatch.setattr("src.pms.guesty.time.sleep", lambda *_a, **_k: None)
    puts = {"n": 0}

    def fake_put(*_a, **_k):
        puts["n"] += 1
        return _Resp(400)

    monkeypatch.setattr("requests.put", fake_put)
    monkeypatch.setattr("requests.get", lambda *_a, **_k: _Resp(200, {"data": {"days": []}}))
    ok, err = client.set_rate("listing1", date(2026, 12, 10), 555.0)
    assert ok is False
    assert puts["n"] == 1
    assert err is not None


def test_set_rate_reconciles_timeout_after_server_side_success(monkeypatch: pytest.MonkeyPatch):
    """Timeout after Guesty applied the PUT must not leave listed_price stale."""
    client = _client()
    monkeypatch.setattr("src.pms.guesty.time.sleep", lambda *_a, **_k: None)

    def fake_put(*_a, **_k):
        raise requests.Timeout("timed out after the write")

    def fake_get(*_a, **_k):
        return _Resp(200, {"data": {"days": [{"date": "2026-12-10", "price": 555.0}]}})

    monkeypatch.setattr("requests.put", fake_put)
    monkeypatch.setattr("requests.get", fake_get)
    ok, err = client.set_rate("listing1", date(2026, 12, 10), 555.0)
    assert ok is True
    assert err is not None and "reconciled" in err
