"""What the operations layer hands the stay-length model (models.ops_aware_stay).

Inputs per anchor night:
  turn_cost     one turnover for the stay (observed median once there is data)
  p_ready(L)    P(both turns around a stay of L nights are ready on time):
                the arrival turn (gap since the previous booked night) times the
                departure turn (gap until the next booked night)
  min_p_ready   below this a candidate is disqualified and a human decides
  risk_premium  dollars charged per unit of (1 - P(ready))

The hook never changes price. Its only effect is a longer suggested min-stay
(source "ops", never pushed) and a reason on the receipt.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from src.ops import OpsProfile
from src.ops.economics import observed_readiness, ready_probability, turn_cost
from src.ops.profiles import load_ops_policy, load_profiles_as_of
from src.ops.turns import build_turn, market_for, weather_buffer
from src.runcache import memo

BOOKED = ("booked", "blocked")


@dataclass
class OpsStayInputs:
    property_id: str
    turn_cost: float
    cost_basis: str
    cost_n: int
    p_ready: Callable[[int], float]
    min_p_ready: float
    risk_premium: float
    min_gain_pct: float = 0.05

    def facts(self, standing: int, chosen: int, ev: Any) -> dict[str, Any]:
        return {
            "turn_cost": self.turn_cost,
            "cost_basis": self.cost_basis,
            "cost_n": self.cost_n,
            "standing": standing,
            "chosen": chosen,
            "p_ready_standing": round(self.p_ready(standing), 3),
            "p_ready_chosen": round(self.p_ready(chosen), 3),
            "per_night_turn_cost_standing": round(self.turn_cost / max(1, standing), 2),
            "per_night_turn_cost_chosen": round(self.turn_cost / max(1, chosen), 2),
            "disqualified": list(ev.disqualified),
        }

    def message(self, standing: int, chosen: int, ev: Any) -> str:
        parts = []
        if chosen != standing:
            parts.append(
                f"A {standing}-night minimum carries a ${self.turn_cost:,.0f} turn "
                f"(${self.turn_cost / max(1, standing):,.0f}/night, {self.cost_basis}) "
                f"versus ${self.turn_cost / max(1, chosen):,.0f}/night at {chosen} nights; "
                f"operations suggests {chosen} (not pushed)"
            )
        if ev.disqualified:
            parts.append(
                "readiness below policy for "
                + ", ".join(f"{n}-night" for n in ev.disqualified)
                + " stays — human review"
            )
        return "; ".join(parts)


def _neighbour_gaps(conn: sqlite3.Connection, property_id: str, anchor: date,
                    horizon: int = 30) -> tuple[int | None, list[date]]:
    """(nights since the previous occupied night, occupied nights ahead)."""
    prev = conn.execute(
        f"""SELECT MAX(stay_date) AS d FROM nightly_inventory
            WHERE property_id=? AND stay_date<? AND stay_date>=?
              AND status IN ({','.join('?' * len(BOOKED))})""",
        (property_id, anchor.isoformat(), (anchor - timedelta(days=horizon)).isoformat(), *BOOKED),
    ).fetchone()
    before = None
    if prev is not None and prev["d"]:
        last = date.fromisoformat(str(prev["d"])[:10])
        before = (anchor - (last + timedelta(days=1))).days
    ahead = [
        date.fromisoformat(str(r["stay_date"])[:10])
        for r in conn.execute(
            f"""SELECT stay_date FROM nightly_inventory
                WHERE property_id=? AND stay_date>? AND stay_date<=?
                  AND status IN ({','.join('?' * len(BOOKED))}) ORDER BY stay_date""",
            (property_id, anchor.isoformat(), (anchor + timedelta(days=horizon)).isoformat(), *BOOKED),
        ).fetchall()
    ]
    return before, ahead


def ops_stay_inputs(conn: sqlite3.Connection, feat: Any, *, as_of: date) -> OpsStayInputs | None:
    """None when the property has no operations profile (the hook then does nothing)."""
    profiles: dict[str, OpsProfile] = memo(
        ("ops_profiles", id(conn), as_of.isoformat()),
        lambda: load_profiles_as_of(conn, as_of)[0],
    )
    profile = profiles.get(feat.property_id)
    if profile is None:
        return None
    ops_policy: dict[str, Any] = memo(("ops_policy",), load_ops_policy)
    observed = memo(("ops_observed_ready", id(conn), as_of.isoformat()),
                    lambda: observed_readiness(conn, profiles, as_of, ops_policy))
    cost = memo(("ops_turn_cost", id(conn), feat.property_id, as_of.isoformat()),
                lambda: turn_cost(conn, profile, as_of=as_of, ops_policy=ops_policy))
    market = market_for(conn, feat.property_id)
    anchor = feat.stay_date
    before, ahead = _neighbour_gaps(conn, feat.property_id, anchor)

    def p_turn(service_date: date, gap: int | None) -> float:
        buf, snow, _ = weather_buffer(conn, market, service_date, as_of, ops_policy)
        turn = build_turn(profile, service_date=service_date, departing="x",
                          arriving=None if gap is None else "y", gap_nights=gap,
                          buffer_minutes=buf, snow=snow)
        return ready_probability(turn.slack_minutes, ops_policy, observed).p

    def p_ready(length: int) -> float:
        p_arrive = p_turn(anchor, before)
        checkout = anchor + timedelta(days=length)
        nxt = next((d for d in ahead if d >= checkout), None)
        p_depart = p_turn(checkout, None if nxt is None else (nxt - checkout).days)
        return p_arrive * p_depart

    stay_cfg = ops_policy.get("stay") or {}
    return OpsStayInputs(
        property_id=feat.property_id,
        turn_cost=cost.amount,
        cost_basis=cost.basis,
        cost_n=cost.n,
        p_ready=p_ready,
        min_p_ready=float(stay_cfg.get("min_p_ready", 0.6)),
        risk_premium=float(stay_cfg.get("risk_premium", 0.0)),
        min_gain_pct=float(stay_cfg.get("min_gain_pct", 0.05)),
    )
