"""One simulated day of the Winter Park shopper market.

The world writes the same tables a Guesty sync writes. It does not import the
pricing engine.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

from proving_ground_exam.market.choice import Alternative, choose, stay_nights
from proving_ground_exam.market.competitors import occupancy, static_price, tool_min_stay, tool_price
from proving_ground_exam.market.funnel import cancel_hazard, converts
from proving_ground_exam.market.parameters import daterange, season_of, value_of
from proving_ground_exam.market.rngutil import generator
from proving_ground_exam.market.scrape import observe
from proving_ground_exam.market.shoppers import Shopper, draw_shoppers

HOLIDAY_SPANS = (
    (date(2026, 12, 19), date(2027, 1, 3)),
    (date(2027, 1, 16), date(2027, 1, 19)),
    (date(2027, 2, 13), date(2027, 2, 16)),
)

SIGNAL_KEYS = (
    ("macro.sim_snow", "index", "Snow index used by the market simulator"),
    ("macro.sim_access", "index", "Road-access index used by the market simulator"),
    ("macro.sim_macro", "index", "Consumer-conditions index used by the market simulator"),
)


def _parse(value: str) -> date:
    return date.fromisoformat(value)


class MarketWorld:
    def __init__(
        self,
        cal: dict[str, Any],
        scenario: dict[str, Any],
        seed: int,
        conn: sqlite3.Connection,
        *,
        season_start: date | None = None,
        season_end: date | None = None,
    ):
        self.cal = cal
        self.scenario = scenario
        self.seed = seed
        self.conn = conn
        self.season_start = season_start or _parse(cal["season_start"])
        self.season_end = season_end or _parse(cal["season_end"])
        self.nights = list(daterange(self.season_start, self.season_end))
        self.scenario_name = str(scenario.get("name", "normal"))
        self.median = value_of(cal["median_nightly"])
        self.properties = list(cal["properties"])
        self.comp_ids = list(cal["competitors"])
        if float(scenario.get("supply_extra", 0) or 0) > 0:
            self.comp_ids = [*self.comp_ids, "comp_supply"]
            conn.execute(
                """
                INSERT OR REPLACE INTO comps (comp_id, name, bedrooms, sleeps, platform, active)
                VALUES ('comp_supply', 'Extra supply', 5, 12, 'airbnb', 1)
                """
            )
            for prop in self.properties:
                conn.execute(
                    "INSERT OR IGNORE INTO comp_set_members (property_id, comp_id) VALUES (?, 'comp_supply')",
                    (prop,),
                )
        self.alt_ids = [*self.properties, *self.comp_ids, "outside"]
        self.free: dict[str, set[date]] = {alt: set(self.nights) for alt in (*self.properties, *self.comp_ids)}
        self.listed: dict[tuple[str, date], float] = {}
        self.comp_price: dict[tuple[str, date], float] = {}
        self.comp_booked: dict[str, set[date]] = {cid: set() for cid in self.comp_ids}
        self.reservations: dict[str, dict[str, Any]] = {}
        self.shoppers: list[Shopper] = []
        self.choices: list[dict[str, Any]] = []
        self._pending: list[tuple[date, str, list[date], float, str, int]] = []
        self._yesterday: dict[date, list[float]] = {}
        for prop in self.properties:
            for night in self.nights:
                self.listed[(prop, night)] = self._flat(night)
        self._price_comps(self.season_start)

    def _flat(self, night: date) -> float:
        return value_of(self.cal["flat_price"][season_of(night)])

    def holidays(self) -> list[tuple[date, date]]:
        offset = timedelta(days=int(self.scenario.get("holiday_offset_days", 0) or 0))
        return [(start + offset, end + offset) for start, end in HOLIDAY_SPANS]

    def is_holiday(self, night: date) -> bool:
        return any(start <= night <= end for start, end in self.holidays())

    def climate(self, day: date) -> tuple[float, float, float]:
        sc = self.scenario
        snow = float(sc.get("snow", 0.55))
        access = float(sc.get("access", 0.95))
        macro = float(sc.get("macro", 0.60))
        if (day - self.season_start).days < int(sc.get("late_open_days", 0) or 0):
            snow = min(snow, 0.20)
        early = int(sc.get("early_close_days", 0) or 0)
        if early and day > self.season_end - timedelta(days=early):
            snow = min(snow, 0.15)
        for raw in sc.get("i70_weekends") or []:
            start = _parse(raw)
            if start <= day <= start + timedelta(days=2):
                access = 0.05
        regime = sc.get("regime_on")
        if regime and day >= _parse(regime):
            snow = float(sc.get("regime_snow", snow))
            macro = float(sc.get("regime_macro", macro))
        return snow, access, macro

    def set_own_prices(self, prices: dict[tuple[str, date], float]) -> None:
        """Guest-facing prices. Booked nights keep the price they were sold at."""
        for (prop, night), price in prices.items():
            if night in self.free.get(prop, set()):
                self.listed[(prop, night)] = float(price)
                self.conn.execute(
                    """
                    UPDATE nightly_inventory SET listed_price = ?
                    WHERE property_id = ? AND stay_date = ? AND status = 'available'
                    """,
                    (float(price), prop, night.isoformat()),
                )

    def step(self, day: date) -> None:
        self.begin_day(day)
        self.end_day(day)

    def begin_day(self, day: date) -> tuple[float, float, float]:
        """Cancellations, competitor prices, scrape, and signals. No shoppers yet."""
        self._flush(day)
        self._refresh_leads(day)
        snow, access, macro = self.climate(day)
        self._price_comps(day)
        self._write_scrape(day)
        self._write_signals(day, snow, access, macro)
        self._cancellations(day)
        self.conn.commit()
        return snow, access, macro

    def end_day(self, day: date) -> None:
        """Shoppers arrive and choose against the prices currently on offer."""
        snow, access, macro = self.climate(day)
        den = float(self.scenario.get("den_capacity", 1.0) or 1.0)
        pandemic = float(self.scenario.get("pandemic_factor", 1.0) or 1.0)
        shoppers = draw_shoppers(
            self.cal,
            scenario=self.scenario_name,
            seed=self.seed,
            day=day,
            snow=snow,
            access=access,
            macro=macro,
            den_capacity=den,
            pandemic_factor=pandemic,
            holidays=self.holidays(),
            alternative_ids=self.alt_ids,
        )
        for shopper in shoppers:
            self.shoppers.append(shopper)
            self._apply_choice(day, shopper)
        self.conn.commit()

    def _apply_choice(self, day: date, shopper: Shopper) -> None:
        # Re-choose with stay-average prices so LOS is priced as a stay.
        nights = stay_nights(shopper.check_in, shopper.los)
        alts: list[Alternative] = [
            Alternative("outside", "outside", 0, 0.0, None),
        ]
        for prop, meta in self.cal["properties"].items():
            if all((prop, night) in self.listed for night in nights):
                nightly = sum(self.listed[(prop, night)] for night in nights) / len(nights)
            else:
                nightly = 10**9
            alts.append(Alternative(prop, "own", int(meta["sleeps"]), value_of(meta["quality"]), nightly))
        for cid in self.comp_ids:
            meta = self.cal["competitors"].get(cid) or {"sleeps": 12, "quality": {"value": 0.8}}
            quality = value_of(meta["quality"]) if isinstance(meta.get("quality"), dict) else 0.8
            if all((cid, night) in self.comp_price for night in nights):
                nightly = sum(self.comp_price[(cid, night)] for night in nights) / len(nights)
            else:
                nightly = 10**9
            alts.append(Alternative(cid, "comp", int(meta.get("sleeps", 12)), quality, nightly))
        alts.append(Alternative("outside", "outside", 0, 0.0, None))
        picked = choose(
            shopper,
            alts,
            free=self.free,
            median=self.median,
            fit_penalty=value_of(self.cal["fit_penalty"]),
            fit_ratio=value_of(self.cal["fit_ratio"]),
            season_end=self.season_end,
        )
        kind = "outside"
        revenue = 0.0
        if picked in self.properties:
            if converts(shopper, self.cal):
                kind = "book"
                revenue = self._book(day, shopper, picked, nights)
            else:
                kind = "inquiry"
                self._inquiry(day, shopper, picked, nights)
        elif picked in self.comp_ids:
            kind = "comp"
            for night in nights:
                self.free[picked].discard(night)
                self.comp_booked[picked].add(night)
        self.choices.append(
            {
                "shopper_id": shopper.shopper_id,
                "segment": shopper.segment,
                "check_in": shopper.check_in.isoformat(),
                "los": shopper.los,
                "party": shopper.party,
                "wtp": shopper.wtp_multiplier,
                "choice": picked,
                "kind": kind,
                "revenue": revenue,
            }
        )

    def _book(self, day: date, shopper: Shopper, prop: str, nights: list[date]) -> float:
        revenue = 0.0
        rid = f"sim-{shopper.shopper_id}"
        for night in nights:
            price = self.listed[(prop, night)]
            revenue += price
            self.free[prop].discard(night)
        self.reservations[rid] = {
            "property_id": prop,
            "check_in": nights[0],
            "nights": nights,
            "status": "confirmed",
            "channel": shopper.channel,
            "party": shopper.party,
            "booked_on": day,
        }
        self._pending.append((day + timedelta(days=self._stale()), rid, nights, revenue, shopper.channel, shopper.party))
        # The pending flush writes sqlite. Truth is already updated.
        if self._stale() == 0:
            self._flush(day)
        return revenue

    def _inquiry(self, day: date, shopper: Shopper, prop: str, nights: list[date]) -> None:
        rid = f"inq-{shopper.shopper_id}"
        self.conn.execute(
            """
            INSERT OR REPLACE INTO reservations (
                reservation_id, property_id, check_in, check_out, nights, status, source,
                confirmed_at, created_at_pms, guest_count, nightly_rate, raw_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid, prop, nights[0].isoformat(), (nights[-1] + timedelta(days=1)).isoformat(),
                len(nights), "inquiry", shopper.channel, None, day.isoformat(),
                shopper.party, None, json.dumps({"kind": "inquiry"}),
            ),
        )

    def _stale(self) -> int:
        return int(self.scenario.get("pms_stale_days", 0) or 0)

    def _flush(self, day: date) -> None:
        still = []
        for visible_on, rid, nights, _revenue, channel, party in self._pending:
            if visible_on > day:
                still.append((visible_on, rid, nights, _revenue, channel, party))
                continue
            res = self.reservations.get(rid)
            if res is None or res["status"] != "confirmed":
                continue
            prop = res["property_id"]
            self.conn.execute(
                """
                INSERT OR REPLACE INTO reservations (
                    reservation_id, property_id, check_in, check_out, nights, status, source,
                    confirmed_at, created_at_pms, guest_count, nightly_rate, raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rid, prop, nights[0].isoformat(), (nights[-1] + timedelta(days=1)).isoformat(),
                    len(nights), "confirmed", channel, visible_on.isoformat(), res["booked_on"].isoformat(),
                    party, None, json.dumps({"kind": "booking"}),
                ),
            )
            for night in nights:
                price = self.listed.get((prop, night))
                self.conn.execute(
                    """
                    UPDATE nightly_inventory
                    SET status='booked', booked_price=?, booked_at=?, reservation_id=?,
                        channel=?, guest_count=?
                    WHERE property_id=? AND stay_date=?
                    """,
                    (price, visible_on.isoformat(), rid, channel, party, prop, night.isoformat()),
                )
        self._pending = still

    def _cancellations(self, day: date) -> None:
        for rid, res in list(self.reservations.items()):
            if res["status"] != "confirmed":
                continue
            lead = (res["check_in"] - day).days
            if lead <= 0:
                continue
            hazard = cancel_hazard(lead, self.cal)
            draw = float(generator(self.scenario_name, self.seed, "cancel", rid, day.isoformat()).random())
            if draw >= hazard:
                continue
            res["status"] = "canceled"
            for night in res["nights"]:
                self.free[res["property_id"]].add(night)
            self.conn.execute(
                "UPDATE reservations SET status='canceled', confirmed_at=NULL WHERE reservation_id=?",
                (rid,),
            )
            self.conn.execute(
                """
                UPDATE nightly_inventory
                SET status='available', booked_price=NULL, booked_at=NULL, reservation_id=NULL
                WHERE reservation_id=?
                """,
                (rid,),
            )

    def _price_comps(self, day: date) -> None:
        price_war = bool(self.scenario.get("price_war"))
        factor = 0.80 if price_war else value_of(self.cal["undercut_factor"])
        medians: dict[date, float] = {}
        for night in self.nights:
            if night < day:
                continue
            others = self._yesterday.get(night) or [self.median]
            medians[night] = float(sorted(others)[len(others) // 2])
        today_quotes: dict[date, list[float]] = {night: [] for night in self.nights if night >= day}
        for cid in self.comp_ids:
            if cid == "comp_supply":
                meta = {"agent": "market_follower", "sleeps": 12}
            else:
                meta = self.cal["competitors"][cid]
            agent = meta["agent"] if cid != "comp_supply" else "market_follower"
            for night in self.nights:
                if night < day:
                    continue
                lead = (night - day).days
                if agent == "static_owner":
                    price = static_price(
                        night, float(str(meta["base_peak"])), float(str(meta["base_other"]))
                    )
                elif agent == "generalized_tool":
                    occ = occupancy(self.comp_booked[cid], day)
                    price = tool_price(
                        night,
                        base=float(str(meta["base"])),
                        holiday=self.is_holiday(night),
                        occupancy_30=occ,
                        lead_days=lead,
                        price_war=price_war,
                    )
                    _ = tool_min_stay(night, lead, occ < 0.40)
                elif agent == "undercutter":
                    price = round(factor * medians[night], 2)
                else:
                    price = round(0.97 * medians[night], 2) if cid == "comp_supply" else round(medians[night], 2)
                self.comp_price[(cid, night)] = price
                if agent != "undercutter":
                    today_quotes[night].append(price)
        for night, quotes in today_quotes.items():
            self._yesterday[night] = quotes or [self.median]

    def _write_scrape(self, day: date) -> None:
        outage = bool(self.scenario.get("scrape_outage"))
        log_sigma = value_of(self.cal["scrape_log_sigma"])
        missing = value_of(self.cal["scrape_missing_prob"])
        rng = generator(self.scenario_name, self.seed, "scrape", day.isoformat())
        rows = []
        for cid in self.comp_ids:
            for night in self.nights:
                if night < day:
                    continue
                price, status = observe(
                    self.comp_price[(cid, night)],
                    rng,
                    log_sigma=log_sigma,
                    missing_prob=missing,
                    outage=outage,
                )
                rows.append((cid, day.isoformat(), night.isoformat(), price, 1 if status == "ok" else 0, status, "sim"))
        self.conn.executemany(
            """
            INSERT INTO comp_snapshots (
                comp_id, as_of, stay_date, listed_price, available, scrape_status, source, capture_method
            ) VALUES (?,?,?,?,?,?,?, 'simulated_scrape')
            ON CONFLICT(comp_id, as_of, stay_date) DO UPDATE SET
                listed_price=excluded.listed_price,
                available=excluded.available,
                scrape_status=excluded.scrape_status
            """,
            rows,
        )

    def _write_signals(self, day: date, snow: float, access: float, macro: float) -> None:
        market = self.cal["market_id"]
        for key, value in (
            ("macro.sim_snow", snow),
            ("macro.sim_access", access),
            ("macro.sim_macro", macro),
        ):
            self.conn.execute(
                """
                INSERT INTO signal_observations (
                    signal_key, market_id, observed_at, effective_date, horizon_days,
                    value, confidence, quality, provenance_url
                ) VALUES (?,?,?,?,0,?,1,'ok','simulator')
                ON CONFLICT(signal_key, market_id, observed_at, effective_date, horizon_days)
                DO UPDATE SET value=excluded.value
                """,
                (key, market, day.isoformat(), day.isoformat(), value),
            )

    def _refresh_leads(self, day: date) -> None:
        self.conn.execute(
            """
            UPDATE nightly_inventory
            SET lead_time_days = CAST(julianday(stay_date) - julianday(?) AS INTEGER)
            WHERE stay_date >= ?
            """,
            (day.isoformat(), day.isoformat()),
        )


def seed_market_db(conn: sqlite3.Connection, cal: dict[str, Any], start: date, end: date) -> None:
    """Insert homes, competitor shells, and empty calendars. No engine imports."""
    conn.execute(
        """
        INSERT OR IGNORE INTO markets (market_id, name, ring, county, active)
        VALUES ('grand_home', 'Winter Park / Fraser', 'home', 'Grand', 1)
        """
    )
    market_id = str(cal.get("market_id") or "grand_home")
    if market_id != "grand_home":
        # A portability market is a watch ring so it does not become the home market.
        conn.execute(
            """
            INSERT OR IGNORE INTO markets (market_id, name, ring, county, active)
            VALUES (?, ?, 'watch', NULL, 1)
            """,
            (market_id, market_id),
        )
    for key, _unit, description in SIGNAL_KEYS:
        conn.execute(
            """
            INSERT INTO signal_definitions (
                signal_key, category, unit, cadence, source, status, description, collector
            ) VALUES (?, 'macro', 'index', 'daily', 'simulator', 'shadow', ?, 'market_sim')
            ON CONFLICT(signal_key) DO NOTHING
            """,
            (key, description),
        )
    for prop, meta in cal["properties"].items():
        conn.execute(
            """
            INSERT OR REPLACE INTO properties (
                property_id, name, bedrooms, bathrooms, base_ceiling_rate, min_floor_rate,
                max_ceiling_rate, max_occupancy, owner_id, market_id, timezone
            ) VALUES (?,?,?,?,?,?,?,?,?,?, 'America/Denver')
            """,
            (
                prop, meta["name"], meta["bedrooms"], 4.0, meta["base"], meta["floor"],
                meta["ceiling"], meta["sleeps"], meta["owner_id"], cal["market_id"],
            ),
        )
    for cid, meta in cal["competitors"].items():
        conn.execute(
            """
            INSERT OR REPLACE INTO comps (comp_id, name, bedrooms, sleeps, platform, active)
            VALUES (?,?,?,?, 'airbnb', 1)
            """,
            (cid, cid, 5, meta["sleeps"]),
        )
        for prop in cal["properties"]:
            conn.execute(
                "INSERT OR IGNORE INTO comp_set_members (property_id, comp_id) VALUES (?,?)",
                (prop, cid),
            )
        flat = {name: value_of(node) for name, node in cal["flat_price"].items()}
    rows = []
    for prop in cal["properties"]:
        for night in daterange(start, end):
            price = flat[season_of(night)]
            rows.append((prop, night.isoformat(), price, "available", night.weekday(), (night - start).days))
    conn.executemany(
        """
        INSERT OR REPLACE INTO nightly_inventory (
            property_id, stay_date, listed_price, status, day_of_week, lead_time_days, evidence_kind
        ) VALUES (?,?,?,?,?,?, 'skeleton')
        """,
        rows,
    )
    conn.commit()
