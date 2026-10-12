"""Property premium controls, provenance, and diagnostic benchmarks."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pytest

from proving_ground_exam.market.choice import Alternative, Shopper, loss_reason
from proving_ground_exam.market.parameters import load_calibration
from src.ceiling import compute_ceiling
from src.config import load_policy, load_policy_overlay
from src.db import connect, init_db
from src.features import build_features_for_property
from src.proving_ground.market_loop import assert_outside_icloud, path_is_icloud, run_pool
from src.proving_ground.run_lock import market_run_lock, stop_market_run
from src.proving_ground.sensitivity import apply_sensitivity, load_sensitivity


ROOT = Path(__file__).resolve().parents[2]


def test_icloud_output_is_refused():
    assert path_is_icloud(Path("/Users/x/Library/Mobile Documents/com~apple~CloudDocs/repo"))
    with pytest.raises(RuntimeError, match="iCloud"):
        assert_outside_icloud(Path("/Users/x/Library/Mobile Documents/repo"))


def test_run_lock_blocks_a_live_owner_and_stop_refuses_a_recycled_command(tmp_path: Path):
    import subprocess

    proc = subprocess.Popen(["sleep", "60"])
    lock = tmp_path / "RUN.lock"
    try:
        lock.write_text(
            json.dumps({"pid": proc.pid, "output_dir": "/tmp/other-market"}),
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="already running"):
            with market_run_lock(tmp_path / "out", path=lock):
                pass
        with pytest.raises(RuntimeError, match="no longer a market"):
            stop_market_run(path=lock)
        assert lock.exists()
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_stop_rejects_a_recycled_pid_even_if_command_contains_market(tmp_path: Path):
    import subprocess
    from src.proving_ground.run_lock import _process_start

    proc = subprocess.Popen(["sleep", "60"])
    lock = tmp_path / "RUN.lock"
    try:
        lock.write_text(
            json.dumps({
                "pid": proc.pid,
                "process_start": "a different process start",
                "output_dir": "/tmp/other-market",
            }),
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="recycled"):
            stop_market_run(path=lock)
        assert lock.exists()
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_run_lock_claim_is_atomic_for_two_starts(tmp_path: Path):
    import threading
    from src.proving_ground.run_lock import _claim_lock

    lock = tmp_path / "RUN.lock"
    results: list[str] = []

    def attempt() -> None:
        try:
            _claim_lock(lock, {"pid": 1})
            results.append("claimed")
            import time
            time.sleep(0.05)
        except FileExistsError:
            results.append("blocked")

    first = threading.Thread(target=attempt)
    second = threading.Thread(target=attempt)
    first.start(); second.start()
    first.join(); second.join()
    assert sorted(results) == ["blocked", "claimed"]
    lock.unlink()


def test_stop_removes_a_stale_lock(tmp_path: Path):
    lock = tmp_path / "RUN.lock"
    lock.write_text(json.dumps({"pid": 2**31 - 1, "output_dir": "/tmp/gone"}), encoding="utf-8")
    message = stop_market_run(path=lock)
    assert "already gone" in message
    assert not lock.exists()


def test_provenance_records_untracked_files(tmp_path: Path):
    output = tmp_path / "prov"
    paths = run_pool("normal", 1, "flat", workers=1, output_dir=output, max_days=2)
    config = json.loads(Path(paths["manifest"]).read_text())["provenance"]["config"]
    assert "git_untracked" in config
    assert isinstance(config["git_untracked"], list)
    assert "git_dirty_tracked" in config
    assert config["git_diff_sha256"]
    assert (output / "hindsight_oracle.csv").exists()
    oracle = (output / "hindsight_oracle.csv").read_text()
    assert "non-deployable" in oracle


def test_property_season_ceiling_in_default_policy():
    policy = load_policy()
    assert "property_premium" not in policy["ceiling"]
    caps = policy["ceiling"]["property_season_ceiling"]
    assert caps["cloud_9"]["peak_ski"] == 1035
    assert caps["overlook_ridge"]["peak_ski"] == 916
    assert not (policy["ceiling"].get("holiday_pool") or {}).get("enabled")
    assert not (policy["ceiling"].get("thin_anchor_guard") or {}).get("enabled")
    overlay = load_policy_overlay(ROOT / "config/policies/candidates/cloud9_lower_peak_ceiling.yaml")
    assert overlay["ceiling"]["property_season_ceiling"]["cloud_9"]["peak_ski"] == 1035
    assert not any(
        isinstance(spec, dict) and spec.get("enabled")
        for spec in overlay.get("models", {}).values()
    )


def test_season_ceiling_cap_binds_only_when_configured(tmp_path: Path):
    path = tmp_path / "cap.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('cloud_9','Cloud 9',6,5.5,'[]',1035,440,2000,'America/Denver','x')"""
        )
        for year, price in ((2023, 1800), (2024, 1800), (2025, 1800)):
            for offset in range(8):
                stay = date(year, 12, 20) + __import__("datetime").timedelta(days=offset)
                conn.execute(
                    """INSERT INTO nightly_inventory
                       (property_id, stay_date, listed_price, booked_price, status, day_of_week, booked_at)
                       VALUES ('cloud_9', ?, ?, ?, 'booked', ?, ?)""",
                    (stay.isoformat(), price, price, stay.weekday(), f"{year}-06-01"),
                )
        conn.commit()
        target = date(2026, 12, 24)
        conn.execute(
            """INSERT INTO nightly_inventory
               (property_id, stay_date, listed_price, status, day_of_week)
               VALUES ('cloud_9', ?, 900, 'available', ?)""",
            (target.isoformat(), target.weekday()),
        )
        conn.commit()
        feat = build_features_for_property(conn, "cloud_9", target, target, as_of=date(2026, 11, 1))[0]
        uncapped = copy.deepcopy(load_policy())
        uncapped["ceiling"].pop("property_season_ceiling", None)
        plain = compute_ceiling(conn, feat, uncapped, as_of=date(2026, 11, 1))
        capped = compute_ceiling(conn, feat, load_policy(), as_of=date(2026, 11, 1))
    assert plain.ceiling_price > 1035
    assert capped.ceiling_price <= 1035
    assert plain.booked_sample_size > 0
    assert plain.band_low is not None and plain.band_low < plain.band_high


def test_sensitivity_does_not_edit_the_official_calibration(tmp_path: Path):
    official = load_calibration()
    spec = load_sensitivity(ROOT / "config/market_sim/sensitivity/arrival_low.yaml")
    updated = apply_sensitivity(official, spec)
    assert updated["arrival_mean"]["value"] == 2.0
    assert load_calibration()["arrival_mean"]["value"] == 3.2
    steeper = apply_sensitivity(
        official, load_sensitivity(ROOT / "config/market_sim/sensitivity/price_coef_steeper.yaml")
    )
    assert steeper["segments"]["families_at_holidays"]["price_coef"]["peak_ski"] == pytest.approx(-1.10 * 1.25)


def test_loss_reason_separates_price_availability_and_fit():
    shopper = Shopper(
        shopper_id="s",
        segment="families",
        check_in=date(2026, 12, 24),
        los=2,
        party=4,
        channel="airbnb",
        wtp_multiplier=1.2,
        price_coef=-1.4,
        gumbels={},
        convert_u=0.0,
        decision_day=date(2026, 11, 1),
    )
    nights = {date(2026, 12, 24), date(2026, 12, 25)}
    own = Alternative("cloud_9", "own", 15, 0.95, 820)
    cheaper = Alternative("summit_haus", "own", 16, 1.0, 800)
    outside = Alternative("outside", "outside", 0, 0.0, None)
    free = {"cloud_9": set(nights), "summit_haus": set(nights)}
    kwargs = dict(
        free=free, median=700, fit_penalty=-1.2, fit_ratio=0.35, season_end=date(2027, 4, 29),
    )
    roomy = Shopper(**{**shopper.__dict__, "party": 10})
    assert loss_reason(roomy, own, cheaper, **kwargs) == "price"
    blocked = {**kwargs, "free": {"cloud_9": set()}}
    assert loss_reason(roomy, own, outside, **blocked) == "unavailable"
    above = Alternative("cloud_9", "own", 15, 0.95, 5000)
    assert loss_reason(roomy, above, cheaper, **kwargs) == "above_wtp"
    assert loss_reason(roomy, own, outside, **kwargs) == "outside"
    small = Shopper(**{**shopper.__dict__, "party": 3})
    wide = Alternative("cloud_9", "own", 20, 2.0, 400)
    narrow = Alternative("summit_haus", "own", 6, 0.5, 700)
    fit_kwargs = {**kwargs, "fit_penalty": -3.0}
    assert loss_reason(small, wide, narrow, **fit_kwargs) == "fit"


def test_diagnostic_policy_and_choice_trace(tmp_path: Path):
    from src.proving_ground.market_loop import run_grid

    output = tmp_path / "diag"
    run_grid(
        "normal", 1, ("engine", "property_flat", "flat"),
        workers=1, output_dir=output, max_days=2, retain_dbs=True,
    )
    db = output / "dbs" / "normal_engine_1.db"
    conn = connect(db)
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM sim_choice_trace").fetchone()["n"]
        reasons = {row["reason"] for row in conn.execute("SELECT DISTINCT reason FROM sim_choice_trace")}
    finally:
        conn.close()
    assert count > 0
    assert reasons & {"booked", "above_wtp", "price", "unavailable", "inquiry", "fit", "other", "comp"} or reasons
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("property_diagnostics", ROOT / "scripts" / "property_diagnostics.py")
    diag = module_from_spec(spec)
    spec.loader.exec_module(diag)
    candidate = ROOT / "config/policies/candidates/cloud9_lower_peak_ceiling.yaml"
    report = diag.diagnose(output, "normal", policy_path=candidate)
    assert report["properties"]
    assert report["choice_trace_rows"] == count
    assert report["policy_path"] == str(candidate)
