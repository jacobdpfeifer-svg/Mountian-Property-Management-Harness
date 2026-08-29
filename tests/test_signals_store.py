"""WP-01 acceptance: leak-free as_of reads and idempotent writers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.db import connect, init_db
from src.signals.store import Observation, SignalDefinition, SignalStore


@pytest.fixture()
def store(tmp_path: Path) -> SignalStore:
    db = tmp_path / "wp01.db"
    init_db(db)
    conn = connect(db)
    return SignalStore(conn)


def test_markets_seeded_for_all_five_rings(store: SignalStore):
    markets = store.list_markets()
    ids = {m["market_id"] for m in markets}
    assert ids >= {
        "grand_home",
        "grand_valley",
        "summit",
        "clear_creek_eagle",
        "routt",
    }
    home = store.get_market("grand_home")
    assert home is not None
    assert "335:CO:SNTL" in home["snotel_stations"]


def test_as_of_cannot_return_later_observed_row(store: SignalStore):
    """Even when effective_date is earlier, a later observed_at must not leak."""
    store.upsert_definition(
        SignalDefinition(
            signal_key="swe_in",
            category="conditions",
            unit="inches",
            cadence="daily",
            source="test",
        )
    )
    store.write_observations(
        [
            Observation(
                signal_key="swe_in",
                market_id="grand_home",
                observed_at="2025-12-20",
                effective_date="2025-12-20",
                value=10.0,
                quality="ok",
            ),
            # March revision of a December effective_date — classic lookahead trap
            Observation(
                signal_key="swe_in",
                market_id="grand_home",
                observed_at="2026-03-15",
                effective_date="2025-12-20",
                value=12.2,
                quality="ok",
            ),
        ]
    )
    mid = store.read_observations(
        as_of="2025-12-25",
        signal_key="swe_in",
        market_id="grand_home",
        effective_date="2025-12-20",
    )
    assert len(mid) == 1
    assert mid[0]["value"] == 10.0
    assert mid[0]["observed_at"] == "2025-12-20"

    latest = store.latest_observation(
        as_of="2025-12-25",
        signal_key="swe_in",
        market_id="grand_home",
        effective_date="2025-12-20",
    )
    assert latest is not None
    assert latest["value"] == 10.0

    after = store.latest_observation(
        as_of="2026-03-20",
        signal_key="swe_in",
        market_id="grand_home",
        effective_date="2025-12-20",
    )
    assert after is not None
    assert after["value"] == 12.2


def test_write_observations_idempotent(store: SignalStore):
    store.upsert_definition(
        SignalDefinition(
            signal_key="swe_in",
            category="conditions",
            unit="inches",
            cadence="daily",
            source="test",
        )
    )
    obs = Observation(
        signal_key="swe_in",
        market_id="grand_home",
        observed_at="2025-12-20",
        effective_date="2025-12-20",
        value=9.5,
    )
    store.write_observations([obs])
    store.write_observations([obs])
    rows = store.read_observations(
        as_of="2025-12-20", signal_key="swe_in", market_id="grand_home"
    )
    assert len(rows) == 1

    updated = Observation(
        signal_key="swe_in",
        market_id="grand_home",
        observed_at="2025-12-20",
        effective_date="2025-12-20",
        value=9.7,
    )
    store.write_observations([updated])
    rows = store.read_observations(
        as_of="2025-12-20", signal_key="swe_in", market_id="grand_home"
    )
    assert len(rows) == 1
    assert rows[0]["value"] == 9.7
