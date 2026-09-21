"""Stage B coverage: src/signals/orchestrator.py and src/signals/analyst.py were 0%
covered per the Step 0 triage map. These tests exercise the daily-cycle orchestration
loop (including failure isolation) and the human-facing brief generators, and trace a
value from a collector observation through to a persisted signal_features row — the
handoff `analyst.py` and downstream ceiling/bookprob code actually read.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.db import connect, init_db
from src.signals.analyst import narrate_anomaly, resort_brief, weekly_brief
from src.signals.collector import get_collector
from src.signals.orchestrator import run_daily_cycle
from src.signals.store import SignalStore

FIXTURE = Path(__file__).parent / "fixtures" / "signals"
CDOT_FIX = FIXTURE / "cdot_closure.json"


@pytest.fixture()
def store(tmp_path: Path) -> SignalStore:
    db = tmp_path / "orch.db"
    init_db(db)
    return SignalStore(connect(db))


# --------------------------------------------------------------- run_daily_cycle


def test_unknown_collector_in_schedule_is_reported_not_raised(store: SignalStore):
    report = run_daily_cycle(
        store,
        date(2024, 12, 1),
        schedule=[("does_not_exist", ["grand_home"])],
    )
    assert any("unknown collector does_not_exist" in f for f in report["failures"])
    # The cycle still proceeds to build the resort_ops forecast afterward.
    assert "resort_ops" in report


def test_cdot_fixture_collector_runs_and_is_recorded(store: SignalStore):
    import src.signals.collectors  # noqa: F401 — register

    report = run_daily_cycle(
        store,
        date(2023, 12, 22),
        schedule=[("cdot", ["grand_home"])],
        collector_kwargs={"cdot": {"fixture_path": CDOT_FIX, "sleep": lambda _s: None}},
    )
    assert len(report["runs"]) == 1
    run = report["runs"][0]
    assert run["collector"] == "cdot"
    assert run["market_id"] == "grand_home"
    assert run["status"] == "ok"
    assert run["written"] > 0
    # And the observation is actually readable back through the leak-free store API —
    # the same path src/signals/features/access.py uses downstream.
    rows = store.read_observations(
        as_of="2023-12-22", signal_key="cdot.access_risk", qualities=["ok"]
    )
    assert float(rows[0]["value"]) == 1.0


def test_broken_collector_failure_is_isolated_and_cycle_continues(store: SignalStore):
    """A collector that fails validation must not stop the rest of the schedule."""
    import src.signals.collectors  # noqa: F401 — register

    report = run_daily_cycle(
        store,
        date(2024, 12, 1),
        schedule=[
            ("broken_fixture", ["grand_home"]),
            ("cdot", ["grand_home"]),
        ],
        collector_kwargs={
            "broken_fixture": {"sleep": lambda _s: None},
            "cdot": {"fixture_path": CDOT_FIX, "sleep": lambda _s: None},
        },
    )
    statuses = {r["collector"]: r["status"] for r in report["runs"]}
    assert statuses["broken_fixture"] == "failed"
    assert statuses["cdot"] == "ok"
    assert any("broken_fixture" in f for f in report["failures"])


def test_collector_construction_error_does_not_crash_whole_cycle(store: SignalStore):
    """Regression test for a real bug found in this audit: `cls(store, **kwargs)` used
    to run OUTSIDE the try/except that guards `coll.run(...)`, so a single bad
    collector_kwargs entry (e.g. a typo'd kwarg, or any constructor that raises)
    raised out of run_daily_cycle entirely and skipped every collector scheduled
    after it, plus the resort_ops feature build. Construction is now inside the
    per-collector guard, matching collector.py's own stated design: "collectors
    must degrade, not crash the run."
    """
    import src.signals.collectors  # noqa: F401 — register

    report = run_daily_cycle(
        store,
        date(2024, 12, 1),
        schedule=[
            ("cdot", ["grand_home"]),  # bad kwarg -> TypeError on construction
            ("intent", ["grand_home"]),  # must still run afterward
        ],
        collector_kwargs={
            "cdot": {"not_a_real_kwarg": True},
            "intent": {"fixture_path": FIXTURE / "intent_search.json", "sleep": lambda _s: None},
        },
    )
    assert any(
        "cdot" in f and "failed to construct" in f for f in report["failures"]
    )
    statuses = {r["collector"]: r["status"] for r in report["runs"]}
    assert statuses.get("intent") == "ok"
    # The cycle still reaches the resort_ops build at the end.
    assert "resort_ops" in report


def test_resort_ops_feature_is_written_and_persisted(store: SignalStore):
    report = run_daily_cycle(store, date(2024, 1, 15), schedule=[])
    assert report["resort_ops"]["built_for"] == "2024-01-15"
    assert report["resort_ops"]["surface_label"]
    # Confirm the feature actually landed in signal_features (what analyst.py and any
    # future consumer reads), not just returned in the report dict.
    row = store.read_feature(
        as_of=date(2024, 1, 15),
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 15),
    )
    assert row is not None
    assert 0.0 <= float(row["value"]) <= 1.0


# --------------------------------------------------------------------- analyst.py


def test_resort_brief_runs_with_empty_store(store: SignalStore):
    text = resort_brief(store, date(2024, 1, 15))
    assert "cannot change prices" in text
    assert "Mountain status" in text
    assert "No resort snapshot yet" in text


def test_resort_brief_reports_berthoud_closure(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    coll = get_collector("cdot")(store, fixture_path=CDOT_FIX, sleep=lambda _s: None)
    coll.run(date(2023, 12, 22), "grand_home")
    text = resort_brief(store, date(2023, 12, 22))
    assert "US-40 Berthoud Pass: **CLOSED**" in text


def test_weekly_brief_runs_with_empty_store(store: SignalStore):
    text = weekly_brief(store, date(2024, 1, 15))
    assert "cannot change prices" in text
    assert "No signal runs yet" in text
    assert "None active yet" in text
    assert "SQI kill switch" in text


def test_weekly_brief_lists_recent_runs_and_active_signals(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    coll = get_collector("cdot")(store, fixture_path=CDOT_FIX, sleep=lambda _s: None)
    coll.run(date(2023, 12, 22), "grand_home")
    store.set_status("cdot.access_risk", "active")
    text = weekly_brief(store, date(2023, 12, 22))
    assert "cdot" in text
    assert "cdot.access_risk" in text


def test_narrate_anomaly_no_prior_reports_value(store: SignalStore):
    store.write_feature(
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 15),
        as_of=date(2024, 1, 15),
        value=0.42,
        confidence=0.8,
        inputs={"x": 1},
    )
    msg = narrate_anomaly(
        store,
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 15),
        as_of=date(2024, 1, 15),
    )
    assert msg is not None
    assert "no prior" in msg
    assert "0.420" in msg


def test_narrate_anomaly_below_threshold_is_silent(store: SignalStore):
    store.write_feature(
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 14),
        as_of=date(2024, 1, 14),
        value=0.40,
        confidence=0.8,
        inputs={"x": 1},
    )
    store.write_feature(
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 15),
        as_of=date(2024, 1, 15),
        value=0.42,
        confidence=0.8,
        inputs={"x": 1},
    )
    msg = narrate_anomaly(
        store,
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 15),
        as_of=date(2024, 1, 15),
        threshold=0.15,
    )
    assert msg is None


def test_narrate_anomaly_above_threshold_reports_delta(store: SignalStore):
    store.write_feature(
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 14),
        as_of=date(2024, 1, 14),
        value=0.10,
        confidence=0.8,
        inputs={"x": 1},
    )
    store.write_feature(
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 15),
        as_of=date(2024, 1, 15),
        value=0.60,
        confidence=0.8,
        inputs={"x": 1},
    )
    msg = narrate_anomaly(
        store,
        feature_key="resort.closure_risk",
        market_id="grand_home",
        effective_date=date(2024, 1, 15),
        as_of=date(2024, 1, 15),
        threshold=0.15,
    )
    assert msg is not None
    assert "+0.500" in msg
