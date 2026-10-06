"""Operations scenarios on the shopper market (audit Stage 4). SIMULATED, never realized.

Each scenario has a ground truth (what is really broken, how many crew minutes
really exist each day) and an observed side (the events, transitions, capacity
rows, signals, and feed runs the operations layer would actually record). The
market world prices and books as usual; this module only

  * records the observed side into the job database each morning,
  * plays the person who follows ops recommendations in the ops-on arms
    (closes nights the system says are out of service, reopens them when
    verified, and never applies a blocked recommendation), and
  * in the stay arm, has shoppers respect the ops-suggested minimum stay, as if
    a person had applied it, so demand lost to a longer minimum is visible.

Arms (all on the same shopper seed):
  off    operations.readiness_gate off; every non-blocked recommendation applied
  on     default flags (gate on, ops_aware_stay off)
  stay   gate on and models.ops_aware_stay on (a policy copy, never the default)
  flat   the market loop's flat seasonal rate, for the flat-baseline comparison

Existing market code (proving_ground_exam/market, market_loop.py) is used, not
changed. Every number this module produces is simulated.
"""

from __future__ import annotations

import copy
import json
import random
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from proving_ground_exam.market.parameters import load_calibration, load_scenario
from proving_ground_exam.market.scoring import realized
from proving_ground_exam.market.world import MarketWorld, seed_market_db
from src.compose import generate_recommendations
from src.config import load_policy
from src.ops import AssetEvent
from src.ops.db import ensure_ops_tables, record_asset_event
from src.ops.economics import turn_cost, turn_load_minutes
from src.ops.profiles import load_ops_policy, load_profiles, store_profiles
from src.ops.readiness import (
    AT_RISK,
    INSPECTION_REQUIRED,
    OUT_OF_SERVICE,
    REMEDIATION,
    RESTRICTING,
    auto_escalate,
    state_for_night,
    transition,
)
from src.ops.turns import derive_turns
from src.pacing import take_snapshot

WINDOW_DAYS = 76  # 2026-11-01 .. 2027-01-15: the Christmas peak and the January turn.
ARMS = ("off", "on", "stay", "flat")
OPS_SCENARIOS = (
    "saturday_cleaner_noshow", "hot_tub_failure", "storm_road_closure",
    "sensor_false_positive", "stale_task_feed", "crew_double_booked",
    "permit_expires_midseason", "owner_stay_turn", "back_to_back_holiday",
)
WORLDS = ("normal", "holiday_shift", "den_capacity_cut")  # the last two are held out
LEAD = "Dana Ops"  # the simulated operations lead (a named person)


# ------------------------------------------------------------------ truth


@dataclass
class Truth:
    """What really happened. The ops layer never reads this."""

    crew_minutes: dict[date, float] = field(default_factory=dict)  # all zones, one crew
    broken: dict[str, set[date]] = field(default_factory=dict)      # nights not guest-ready
    needs_human: list[str] = field(default_factory=list)            # situations a person must act on
    notes: dict[str, Any] = field(default_factory=dict)

    def capacity(self, day: date, base: float) -> float:
        return self.crew_minutes.get(day, base)

    def is_broken(self, prop: str, night: date) -> bool:
        return night in self.broken.get(prop, set())


def _at(day: date, hour: int, minute: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, minute).isoformat()


def _event(conn, prop: str, system: str, at: str, severity: str, source: str, ref: str,
           *, start: date | None = None, end: date | None = None, reading: dict | None = None) -> str:
    event_id, _ = record_asset_event(conn, AssetEvent(
        property_id=prop, system_type=system, observed_at=at, severity=severity,
        source_type=source, source_ref=ref, reading=reading or {},
        effective_from=start.isoformat() if start else None,
        effective_to=end.isoformat() if end else None,
    ))
    return event_id


def _signal(conn, key: str, value: float, effective: date, observed: date) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO signal_definitions (signal_key, category, unit, cadence, source, status)
           VALUES (?,?,?,?,?,?)""", (key, "ops_sim", "x", "daily", "ops_sim", "active"))
    conn.execute(
        """INSERT OR IGNORE INTO signal_observations
               (signal_key, market_id, observed_at, effective_date, horizon_days, value, quality)
           VALUES (?,?,?,?,?,?,'ok')""",
        (key, "grand_home", observed.isoformat(), effective.isoformat(),
         (effective - observed).days, value))


# --------------------------------------------------------------- scenarios


@dataclass
class Spec:
    """One scenario: a truth builder, pre-season bookings, and a daily observer."""

    name: str
    build: Callable[[random.Random], Truth]
    preseason: Callable[["OpsMarketWorld"], None] = lambda world: None
    observe: Callable[[sqlite3.Connection, date, Truth], None] = lambda conn, day, truth: None


SAT = date(2026, 12, 19)
HOT_TUB = date(2026, 12, 22)
STORM = date(2026, 12, 27)
FALSE_ALARM = date(2026, 12, 29)
STALE_FROM = date(2026, 12, 20)
DOUBLE = date(2027, 1, 2)
PERMIT_EXPIRES = date(2027, 1, 10)


def _noshow_truth(rng: random.Random) -> Truth:
    t = Truth(crew_minutes={SAT: 630.0})
    t.needs_human.append("2026-12-19: half the crew missing on a peak Saturday; reassign turns")
    return t


def _noshow_observe(conn, day, truth) -> None:
    if day == SAT:  # the lead types the shortfall in that morning
        conn.execute(
            """INSERT OR IGNORE INTO operations_capacity_snapshots (as_of, service_date, access_zone,
                   available_worker_minutes, committed_worker_minutes, service_type, source)
               VALUES (?,?,?,?,0,'turnover','manual')""", (day.isoformat(), day.isoformat(),
                                                           "northwoods", 630.0))


def _hot_tub_truth(rng: random.Random) -> Truth:
    repair_days = rng.randint(1, 4)
    broken = {HOT_TUB + timedelta(days=i) for i in range(repair_days)}
    t = Truth(broken={"summit_haus": broken}, notes={"repair_days": repair_days})
    t.needs_human.append("2026-12-22: Summit Haus hot tub failed; close or relocate arrivals")
    return t


def _hot_tub_observe(conn, day, truth) -> None:
    repair = HOT_TUB + timedelta(days=int(truth.notes["repair_days"]))
    if day == HOT_TUB:
        ev = _event(conn, "summit_haus", "spa", _at(day, 7), "critical", "sensor", "spa-sensor",
                    start=day, reading={"temp_f": 61})
        auto_escalate(conn, "summit_haus", ev, actor="telemetry", note="spa reading 61F",
                      at=_at(day, 7), effective_from=day)
        # The lead confirms in the morning and estimates a two-day repair.
        transition(conn, "summit_haus", OUT_OF_SERVICE, evidence_event_id=ev, actor=LEAD,
                   at=_at(day, 9), effective_from=day, effective_to=day + timedelta(days=1))
        truth.notes["event"] = ev
    if day == repair:
        ev = str(truth.notes["event"])
        transition(conn, "summit_haus", REMEDIATION, evidence_event_id=ev, actor=LEAD,
                   at=_at(day, 8))
        fixed = _event(conn, "summit_haus", "spa", _at(day, 14), "info", "vendor", "spa-repaired",
                       start=day, reading={"temp_f": 101})
        transition(conn, "summit_haus", "verified_ready", evidence_event_id=fixed, actor=LEAD,
                   at=_at(day, 15))


def _storm_truth(rng: random.Random) -> Truth:
    # Berthoud closed: the crew loses a third of the day to travel.
    t = Truth(crew_minutes={STORM: 840.0})
    t.needs_human.append("2026-12-27: Berthoud closure; warn arrivals, re-sequence turns")
    return t


def _storm_observe(conn, day, truth) -> None:
    if day == STORM - timedelta(days=2):  # forecast known two days ahead
        _signal(conn, "weather.snowfall_sum_cm", 40.0, STORM, day)
        _signal(conn, "cdot.berthoud_closed", 1.0, STORM, day)
        _signal(conn, "weather.temp_mean_c", -20.0, STORM, day)


def _false_alarm_truth(rng: random.Random) -> Truth:
    return Truth()  # nothing is wrong


def _false_alarm_observe(conn, day, truth) -> None:
    if day == FALSE_ALARM:
        ev = _event(conn, "cloud_9", "spa", _at(day, 6), "critical", "sensor", "spa-sensor-glitch",
                    start=day, reading={"temp_f": 40})
        auto_escalate(conn, "cloud_9", ev, actor="telemetry", note="spa reading 40F",
                      at=_at(day, 6), effective_from=day)
        transition(conn, "cloud_9", INSPECTION_REQUIRED, evidence_event_id=ev, actor=LEAD,
                   at=_at(day, 10), effective_from=day, effective_to=day + timedelta(days=1))
        truth.notes["event"] = ev
    if day == FALSE_ALARM + timedelta(days=1):
        ok = _event(conn, "cloud_9", "spa", _at(day, 11), "info", "manual", "spa-inspected-ok",
                    start=day, reading={"temp_f": 102})
        transition(conn, "cloud_9", "verified_ready", evidence_event_id=ok, actor=LEAD,
                   at=_at(day, 11))


def _stale_truth(rng: random.Random) -> Truth:
    # The cleaner skipped Summit Haus on the 22nd; the task feed that would
    # have shown it stopped updating on the 20th.
    t = Truth(broken={"summit_haus": {date(2026, 12, 22)}})
    t.needs_human.append("2026-12-20..23: task feed stale for 72h; a missed clean went unseen")
    return t


def _stale_observe(conn, day, truth) -> None:
    if day == STALE_FROM:
        conn.execute(
            """INSERT OR IGNORE INTO ops_import_runs (run_id, source, kind, started_at, finished_at,
                   status, rows_in, accepted) VALUES (?,?,?,?,?,'ok',0,0)""",
            (f"sim-{day}", "guesty_tasks", "outcomes", _at(day, 6), _at(day, 6)))


def _double_truth(rng: random.Random) -> Truth:
    t = Truth(crew_minutes={DOUBLE: 630.0})
    t.needs_human.append("2027-01-02: one crew booked in two zones; reassign")
    return t


def _permit_truth(rng: random.Random) -> Truth:
    t = Truth()
    t.needs_human.append("2027-01-10: Cloud 9 Fraser registration expires; renew")
    return t


def _permit_preseason(world) -> None:
    from src.compliance import Credential, add_credential

    add_credential(world.conn, Credential(
        property_id="cloud_9", jurisdiction="fraser", credential_type="str_registration",
        identifier="FRASER-STR-SIM-1", issued_at="2026-01-10", expires_at=PERMIT_EXPIRES.isoformat(),
        verification_status="unverified"))


def _owner_preseason(world) -> None:
    world.prebook("summit_haus", date(2026, 12, 26), 7, source="owner", party=8, price=0.0)
    world.prebook("summit_haus", date(2027, 1, 2), 3, source="website", party=12)


def _owner_truth(rng: random.Random) -> Truth:
    return Truth()


def _b2b_preseason(world) -> None:
    for start in (date(2026, 12, 20), date(2026, 12, 23), date(2026, 12, 26), date(2026, 12, 29)):
        world.prebook("summit_haus", start, 3, source="airbnb2", party=14)


SPECS: dict[str, Spec] = {
    "saturday_cleaner_noshow": Spec("saturday_cleaner_noshow", _noshow_truth, observe=_noshow_observe),
    "hot_tub_failure": Spec("hot_tub_failure", _hot_tub_truth, observe=_hot_tub_observe),
    "storm_road_closure": Spec("storm_road_closure", _storm_truth, observe=_storm_observe),
    "sensor_false_positive": Spec("sensor_false_positive", _false_alarm_truth,
                                  observe=_false_alarm_observe),
    "stale_task_feed": Spec("stale_task_feed", _stale_truth, observe=_stale_observe),
    "crew_double_booked": Spec("crew_double_booked", _double_truth),
    "permit_expires_midseason": Spec("permit_expires_midseason", _permit_truth,
                                     preseason=_permit_preseason),
    "owner_stay_turn": Spec("owner_stay_turn", _owner_truth, preseason=_owner_preseason),
    "back_to_back_holiday": Spec("back_to_back_holiday", _owner_truth, preseason=_b2b_preseason),
}


# ------------------------------------------------------------------ world


class OpsMarketWorld(MarketWorld):
    """The market world plus pre-season bookings and an optional min-stay rule."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.min_stay: dict[tuple[str, date], int] = {}
        self.min_stay_refusals = 0
        self.closed: dict[str, set[date]] = {}

    def prebook(self, prop: str, check_in: date, nights: int, *, source: str, party: int,
                price: float | None = None) -> None:
        stay = [check_in + timedelta(days=i) for i in range(nights)]
        rid = f"pre-{prop}-{check_in.isoformat()}"
        self.reservations[rid] = {"property_id": prop, "check_in": check_in, "nights": stay,
                                  "status": "confirmed", "channel": source, "party": party,
                                  "booked_on": self.season_start}
        self.conn.execute(
            """INSERT OR REPLACE INTO reservations (reservation_id, property_id, check_in, check_out,
                   nights, status, source, confirmed_at, created_at_pms, guest_count, nightly_rate,
                   raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, prop, check_in.isoformat(), (check_in + timedelta(days=nights)).isoformat(), nights,
             "confirmed", source, self.season_start.isoformat(), self.season_start.isoformat(),
             party, None, json.dumps({"kind": "prebook"})))
        for night in stay:
            self.free[prop].discard(night)
            booked = self.listed.get((prop, night), self._flat(night)) if price is None else price
            self.conn.execute(
                """UPDATE nightly_inventory SET status=?, booked_price=?, booked_at=?, reservation_id=?,
                       channel=?, guest_count=? WHERE property_id=? AND stay_date=?""",
                ("blocked" if source == "owner" else "booked", booked, self.season_start.isoformat(),
                 rid, source, party, prop, night.isoformat()))
        self.conn.commit()

    def close(self, prop: str, night: date) -> bool:
        if night in self.free.get(prop, set()):
            self.free[prop].discard(night)
            self.closed.setdefault(prop, set()).add(night)
            return True
        return False

    def reopen(self, prop: str, night: date) -> None:
        if night in self.closed.get(prop, set()):
            self.closed[prop].discard(night)
            self.free[prop].add(night)

    def _apply_choice(self, day: date, shopper: Any) -> None:
        held = [p for p in self.properties
                if shopper.los < self.min_stay.get((p, shopper.check_in), 1)
                and shopper.check_in in self.free.get(p, set())]
        for p in held:
            self.free[p].discard(shopper.check_in)
        try:
            before = len(self.reservations)
            super()._apply_choice(day, shopper)
            if held and len(self.reservations) == before and self.choices[-1]["kind"] != "book":
                self.min_stay_refusals += 1
        finally:
            for p in held:
                self.free[p].add(shopper.check_in)


# -------------------------------------------------------------------- job


def arm_policy(arm: str) -> dict[str, Any]:
    policy = copy.deepcopy(load_policy())
    policy.setdefault("operations", {})["readiness_gate"] = arm != "off"
    if arm == "stay":
        policy["models"]["ops_aware_stay"] = {**(policy["models"].get("ops_aware_stay") or {}),
                                              "enabled": True}
    return policy


@dataclass
class OpsResult:
    world: str
    scenario: str
    seed: int
    arm: str
    held_out: bool
    revenue: float
    confirmed_stays: int
    occupancy: float
    turns: int
    turn_cost: float
    net_revenue: float
    violations: int
    unserviceable: int
    arrivals_on_broken_nights: int
    false_restricted_nights: int
    closures: int
    escalations_raised: int
    escalations_needed: int
    min_stay_refusals: int
    ops_min_stay_nights: int
    detail: dict[str, Any]


def _human_closures(world: OpsMarketWorld, conn, day: date, horizon: int = 4) -> int:
    """Follow the closure recommendation: close out-of-service nights soon; reopen on recovery."""
    n = 0
    for prop in world.properties:
        for i in range(horizon):
            night = day + timedelta(days=i)
            state = state_for_night(conn, prop, night, _at(day, 23, 59)).state
            if state in (OUT_OF_SERVICE, REMEDIATION):
                n += int(world.close(prop, night))
            elif night in world.closed.get(prop, set()):
                world.reopen(prop, night)
        for night in sorted(world.closed.get(prop, set())):
            if state_for_night(conn, prop, night, _at(day, 23, 59)).state not in (
                    OUT_OF_SERVICE, REMEDIATION):
                world.reopen(prop, night)
    return n


def _unserviceable(conn, world: OpsMarketWorld, truth: Truth, nights: list[date],
                   ops_policy: dict[str, Any]) -> tuple[int, int, int, float, dict[str, Any]]:
    """Turns the real crew could not finish before a same-day arrival, plus arrivals
    on nights a home was really not guest-ready. Uses the profile estimates."""
    profiles = load_profiles()
    end = nights[-1]
    turns = []
    for prop in world.properties:
        turns.extend(derive_turns(conn, profiles[prop], nights[0], end, as_of=end,
                                  ops_policy=ops_policy, point_in_time_reservations=False))
    base = 3 * 420.0  # the roster: one three-person crew for both zones
    by_day: dict[date, list] = {}
    for t in turns:
        by_day.setdefault(t.service_date, []).append(t)
    short = 0
    over_days = []
    for day, day_turns in sorted(by_day.items()):
        cap = truth.capacity(day, base)
        # Same-day turns first, then the rest; anything past capacity slips a day,
        # which only fails a guest when the turn was same-day.
        day_turns.sort(key=lambda t: (t.gap_nights is None, t.gap_nights or 0))
        used = 0.0
        for t in day_turns:
            used += turn_load_minutes(t, profiles[t.property_id])
            if used > cap and t.same_day:
                short += 1
        if used > cap:
            over_days.append(day.isoformat())
    broken_arrivals = sum(
        1 for r in conn.execute(
            "SELECT property_id, check_in FROM reservations WHERE status='confirmed' AND source<>'owner'")
        if truth.is_broken(r["property_id"], date.fromisoformat(str(r["check_in"])[:10])))
    cost = sum(turn_cost(conn, profiles[t.property_id], as_of=end, ops_policy=ops_policy,
                         snow=t.snow_expected).amount for t in turns
               if t.arriving_reservation is not None)
    owner_turns = [t.turn_id for t in turns if "pre-summit_haus-2026-12-26" in t.turn_id]
    return short, broken_arrivals, len(turns), cost, {"over_capacity_days": over_days,
                                                     "owner_turns": owner_turns}


def run_ops_job(world_name: str, scenario: str, seed: int, arm: str, db_path: Path,
                window_days: int = WINDOW_DAYS) -> OpsResult:
    from src.db import DB_KIND_DEMO, connect, init_db, mark_db_identity

    cal = load_calibration()
    world_doc = load_scenario(world_name)
    spec = SPECS[scenario]
    start = date.fromisoformat(cal["season_start"])
    nights = [start + timedelta(days=i) for i in range(window_days)]
    end = nights[-1]
    rng = random.Random(f"{world_name}|{scenario}|{seed}")
    truth = spec.build(rng)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    init_db(db_path)
    conn = connect(db_path)
    mark_db_identity(conn, DB_KIND_DEMO, "ops_sim", force=True)
    ops_policy = load_ops_policy()
    try:
        ensure_ops_tables(conn)
        # Same truncation as market_loop._dates: the window is the season.
        seed_market_db(conn, cal, start, end)
        store_profiles(conn, load_profiles())
        world = OpsMarketWorld(cal, world_doc, seed, conn, season_start=start, season_end=end)
        spec.preseason(world)
        policy = arm_policy(arm) if arm != "flat" else None
        violations = closures = 0
        restricted_seen: set[tuple[str, date]] = set()
        escalated: set[tuple[str, date]] = set()
        ops_min_nights = 0
        incident_ids: set[str] = set()
        compliance_flagged = False
        for day in nights:
            world.begin_day(day)
            take_snapshot(conn, as_of=day)
            if arm != "flat":
                spec.observe(conn, day, truth)
                conn.commit()
            if arm in ("on", "stay"):
                closures += _human_closures(world, conn, day)
                from src.ops.incidents import scan as incident_scan
                from src.ops.readiness import scan_signal_risk

                scan_signal_risk(conn, day, ops_policy, list(world.properties))
                incident_ids |= {c.incident_id for c in incident_scan(conn, day, ops_policy)}
                if scenario == "permit_expires_midseason" and not compliance_flagged:
                    from src.compliance import check

                    rep = check(conn, day, property_ids=["cloud_9"])
                    compliance_flagged = any(r.credential_type == "str_registration"
                                             and r.status in ("expiring", "expired")
                                             for r in rep.results)
            if arm == "flat":
                world.set_own_prices({(p, n): world._flat(n) for p in world.properties for n in nights})
            else:
                recs, _health = generate_recommendations(
                    conn, day, end, property_ids=list(world.properties), policy=policy,
                    persist=False, allow_past=True, as_of=day, run_id=f"ops-{day}")
                prices = {}
                for rec in recs:
                    state = (state_for_night(conn, rec.property_id, rec.stay_date, _at(day, 23, 59)).state
                             if arm != "off" else "ready")
                    if state in RESTRICTING:
                        restricted_seen.add((rec.property_id, rec.stay_date))
                        # Contract: no automatic change on a restricted night.
                        if rec.autonomy_level == "handle":
                            violations += 1
                        if state in (OUT_OF_SERVICE, REMEDIATION) and rec.status != "blocked":
                            violations += 1
                        if (state == INSPECTION_REQUIRED and rec.listed_price_at_run
                                and rec.recommended_price > rec.listed_price_at_run + 0.01
                                and rec.autonomy_level != "escalate"):
                            violations += 1
                    if any(r["code"] == "readiness" for r in rec.reasons) and rec.autonomy_level in (
                            "escalate", "suggest"):
                        escalated.add((rec.property_id, rec.stay_date))
                    if rec.status == "blocked":
                        continue  # a person holds the price; nothing is applied
                    prices[(rec.property_id, rec.stay_date)] = rec.recommended_price
                    if arm == "stay":
                        key = (rec.property_id, rec.stay_date)
                        if rec.min_stay_source == "ops" and rec.recommended_min_stay:
                            world.min_stay[key] = int(rec.recommended_min_stay)
                            ops_min_nights += 1
                        else:
                            world.min_stay.pop(key, None)
                world.set_own_prices(prices)
            world.end_day(day)
        scores = realized(conn, list(world.properties))
        short, broken_arrivals, n_turns, cost, extra = _unserviceable(conn, world, truth, nights,
                                                                     ops_policy)
        false_restricted = sum(1 for prop, night in restricted_seen
                               if not truth.is_broken(prop, night))
        raised = len(incident_ids) + len({p for p, _ in escalated}) + int(compliance_flagged)
        return OpsResult(
            world=world_name, scenario=scenario, seed=seed, arm=arm,
            held_out=bool(world_doc.get("held_out")),
            revenue=float(scores["revenue"]), confirmed_stays=int(scores["confirmed"]),
            occupancy=float(scores["occupancy"]),
            turns=n_turns, turn_cost=round(cost, 2), net_revenue=round(float(scores["revenue"]) - cost, 2),
            violations=violations, unserviceable=short, arrivals_on_broken_nights=broken_arrivals,
            false_restricted_nights=false_restricted, closures=closures,
            escalations_raised=raised, escalations_needed=len(truth.needs_human),
            min_stay_refusals=world.min_stay_refusals, ops_min_stay_nights=ops_min_nights,
            detail={**extra, "truth": {k: (sorted(d.isoformat() for d in v) if isinstance(v, set) else v)
                                       for k, v in truth.notes.items() if k != "event"},
                    "incidents": sorted(incident_ids), "compliance_flagged": compliance_flagged},
        )
    finally:
        conn.close()


def result_row(r: OpsResult) -> dict[str, Any]:
    row = asdict(r)
    row["detail"] = json.dumps(row["detail"], sort_keys=True)
    return row
