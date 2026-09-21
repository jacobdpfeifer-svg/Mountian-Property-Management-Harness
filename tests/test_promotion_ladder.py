"""src/signals/promotion.py was 57% covered per the Step 0 triage map, with the
apply_promotions status-transition branches and signal_freshness_failures (the
function that folds stale active signals into the guardrails data-health gate —
see docs/rules/AUTONOMY.md) largely untested. These are covered directly here.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.db import connect, init_db
from src.signals.promotion import (
    apply_promotions,
    demote_on_source_break,
    signal_freshness_failures,
    signal_status_at_least,
)
from src.signals.store import SignalDefinition, SignalStore


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "promo.db"
    init_db(db)
    return SignalStore(connect(db))


def _score(store, key, *, sample_size, ic, hit_rate, decision):
    store.write_score(
        signal_key=key,
        horizon_days=14,
        sample_size=sample_size,
        information_coefficient=ic,
        hit_rate=hit_rate,
        ic_ci_low=None,
        ic_ci_high=None,
        decision=decision,
    )


def test_experimental_promotes_to_shadow_on_sample_size_alone(store):
    store.upsert_definition(
        SignalDefinition("test.sig", "test", "ratio", "daily", "fixture", "experimental")
    )
    _score(store, "test.sig", sample_size=35, ic=0.01, hit_rate=0.5, decision="hold")
    actions = apply_promotions(store)
    assert "test.sig: experimental→shadow" in actions
    assert store.get_definition("test.sig")["status"] == "shadow"


def test_shadow_promotes_to_active_when_thresholds_met(store):
    store.upsert_definition(
        SignalDefinition("test.sig", "test", "ratio", "daily", "fixture", "shadow")
    )
    _score(store, "test.sig", sample_size=45, ic=0.08, hit_rate=0.55, decision="promote")
    actions = apply_promotions(store)
    assert "test.sig: shadow→active" in actions
    assert store.get_definition("test.sig")["status"] == "active"


def test_shadow_does_not_promote_below_ic_threshold(store):
    store.upsert_definition(
        SignalDefinition("test.sig", "test", "ratio", "daily", "fixture", "shadow")
    )
    _score(store, "test.sig", sample_size=45, ic=0.01, hit_rate=0.55, decision="promote")
    actions = apply_promotions(store)
    assert actions == []
    assert store.get_definition("test.sig")["status"] == "shadow"


def test_active_demotes_to_deprecated_on_demote_decision(store):
    store.upsert_definition(
        SignalDefinition("test.sig", "test", "ratio", "daily", "fixture", "active")
    )
    _score(store, "test.sig", sample_size=100, ic=-0.05, hit_rate=0.4, decision="demote")
    actions = apply_promotions(store)
    assert "test.sig: active→deprecated" in actions
    assert store.get_definition("test.sig")["status"] == "deprecated"


def test_deprecated_signal_is_skipped_by_rescore_but_visible_to_promotions(store):
    store.upsert_definition(
        SignalDefinition("test.sig", "test", "ratio", "daily", "fixture", "deprecated")
    )
    # No score row at all -> apply_promotions must not crash, just no-op.
    actions = apply_promotions(store)
    assert actions == []


def test_demote_on_source_break_sets_deprecated(store):
    store.upsert_definition(
        SignalDefinition("test.sig", "test", "ratio", "daily", "fixture", "active")
    )
    demote_on_source_break(store, "test.sig")
    assert store.get_definition("test.sig")["status"] == "deprecated"
    # A deprecated signal must fall below the ladder's "shadow" bar so any caller
    # gating on signal_status_at_least immediately stops trusting it.
    assert signal_status_at_least(store, "test.sig", "shadow") is False


def test_signal_status_at_least_unknown_signal_is_false(store):
    assert signal_status_at_least(store, "no.such.signal", "shadow") is False


# ------------------------------------------------------ signal_freshness_failures


def test_freshness_failure_for_active_signal_with_no_observations(store):
    store.upsert_definition(
        SignalDefinition("snotel.swe_pct_normal", "snow", "ratio", "daily", "fixture", "active")
    )
    failures = signal_freshness_failures(store, date(2024, 12, 15))
    assert any("no ok observations" in f for f in failures)


def test_freshness_failure_for_stale_snotel_signal(store):
    from src.signals.store import Observation

    store.upsert_definition(
        SignalDefinition("snotel.swe_pct_normal", "snow", "ratio", "daily", "fixture", "active")
    )
    as_of = date(2024, 12, 15)
    stale_date = as_of - timedelta(days=10)  # snotel_max_age_days default 3
    store.write_observations(
        [
            Observation(
                signal_key="snotel.swe_pct_normal",
                market_id="grand_home",
                observed_at=stale_date,
                effective_date=stale_date,
                value=0.8,
                quality="ok",
            )
        ]
    )
    failures = signal_freshness_failures(store, as_of)
    assert any("stale" in f for f in failures)


def test_no_freshness_failure_for_fresh_active_signal(store):
    from src.signals.store import Observation

    store.upsert_definition(
        SignalDefinition("snotel.swe_pct_normal", "snow", "ratio", "daily", "fixture", "active")
    )
    as_of = date(2024, 12, 15)
    store.write_observations(
        [
            Observation(
                signal_key="snotel.swe_pct_normal",
                market_id="grand_home",
                observed_at=as_of,
                effective_date=as_of,
                value=0.8,
                quality="ok",
            )
        ]
    )
    failures = signal_freshness_failures(store, as_of)
    assert failures == []


def test_cdot_same_day_observation_is_never_flagged_stale_regardless_of_hour(store):
    """Documents a real bug found while writing these tests (see stage report):
    `Observation.__post_init__` calls `_iso(observed_at)`, and `_iso()` truncates a
    datetime to `d.date().isoformat()` — the time-of-day is discarded before the row
    is ever written. CDOT is declared `cadence="hourly"` with
    `data_health.freshness.cdot_max_age_hours: 6` specifically because
    docs/signals/collectors/cdot.py calls Berthoud Pass access "a same-week demand
    cliff no competitor-price feed can observe" — i.e. the whole point of an hourly
    cadence is to catch a closure a few hours old. But because only the calendar
    date survives, an observation taken at 07:00 is bit-for-bit indistinguishable
    from one taken at 23:00 the same day, so `signal_freshness_failures` can never
    catch same-day staleness no matter how many hours have actually elapsed — only
    a *previous calendar day* reading is ever flagged. This is not a narrow fix:
    `SignalStore.read_observations`'s leak-free filter (`observed_at <= ?`) depends
    on `observed_at` and every caller's `as_of` being the same date-only string
    precision (guardrails, bookprob, ceiling, comps all pass `as_of` as a bare
    `date`), so restoring hour precision on `observed_at` without also auditing
    every `as_of` comparator site risks a *different* bug (today's observations
    silently excluded by a lexicographic string compare). Flagged to the Architect
    rather than patched here — this is a store.py contract change with consumers
    outside Stage B, not a self-contained fix."""
    from src.signals.store import Observation

    store.upsert_definition(
        SignalDefinition("cdot.access_risk", "access", "ratio", "hourly", "fixture", "active")
    )
    as_of = date(2024, 12, 15)
    from datetime import datetime

    morning_obs = datetime(2024, 12, 15, 7, 0, 0)  # same calendar day as as_of
    store.write_observations(
        [
            Observation(
                signal_key="cdot.access_risk",
                market_id="grand_home",
                observed_at=morning_obs.isoformat() + "Z",
                effective_date=as_of,
                value=0.0,
                quality="ok",
            )
        ]
    )
    stored = store.read_observations(
        as_of="2024-12-15", signal_key="cdot.access_risk", qualities=["ok"]
    )
    assert stored[0]["observed_at"] == "2024-12-15"  # time-of-day silently dropped

    failures = signal_freshness_failures(store, as_of)
    assert failures == []  # never flagged stale, even if "as_of" were hours later


def test_cdot_freshness_uses_hourly_threshold(store):
    """CDOT is hour-scale (Berthoud access risk changes fast); confirm it is not
    silently checked with the day-scale default and that a 10-hour-old reading
    (well past the 6h policy default) is flagged stale."""
    from src.signals.store import Observation
    from datetime import datetime

    store.upsert_definition(
        SignalDefinition("cdot.access_risk", "access", "ratio", "hourly", "fixture", "active")
    )
    as_of = date(2024, 12, 15)
    old_dt = datetime(2024, 12, 14, 12, 0, 0)  # ~12h before as_of midnight
    store.write_observations(
        [
            Observation(
                signal_key="cdot.access_risk",
                market_id="grand_home",
                observed_at=old_dt.isoformat() + "Z",
                effective_date=as_of,
                value=0.0,
                quality="ok",
            )
        ]
    )
    failures = signal_freshness_failures(store, as_of)
    assert any("cdot.access_risk stale" in f for f in failures)
