"""Consumer indicators start at shadow and cannot be read before they were observed."""

from datetime import date
from pathlib import Path

from src.db import connect, init_db
from src.eval.backtest import assert_no_lookahead
from src.signals.consumer import CONSUMER_INDICATORS, register_consumer_indicators
from src.signals.store import Observation, SignalStore


def test_consumer_indicators_register_at_shadow_and_hide_future_observations(tmp_path: Path):
    path = tmp_path / "signals.db"
    init_db(path)
    with connect(path) as conn:
        keys = register_consumer_indicators(conn)
        assert keys == [item[0] for item in CONSUMER_INDICATORS]
        store = SignalStore(conn)
        for key in keys:
            assert store.get_definition(key)["status"] == "shadow"
        key = keys[0]
        store.write_observations([
            Observation(key, "grand_home", "2026-09-01", "2026-09-01", 0.2),
            Observation(key, "grand_home", "2026-10-15", "2026-10-15", 9.0),
        ])
        assert_no_lookahead(store, date(2026, 9, 29), key)
        visible = store.read_observations(as_of=date(2026, 9, 29), signal_key=key)
        assert [row["observed_at"] for row in visible] == ["2026-09-01"]
