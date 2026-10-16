"""Preregistered field test and realized-profit analysis (workstreams 7 and 9).

Design (docs/field_test/PREREGISTRATION.md explains why):

- Unit: one home x one block of `block_days` consecutive nights. Consecutive
  blocks of a home are paired; inside each pair a coin flip seeded from the
  frozen plan's hash picks which block is treatment (engine price) and which is
  control (current practice). Pairs keep season and demand comparable; the
  seed is unknowable until the plan is frozen.
- Outcome: settled owner net per eligible available night. Eligible = in the
  plan window, not owner-blocked or maintenance-blocked. Each reservation's
  owner net (spine ledger, actual lines only, refunds and cancellation income
  included) is spread evenly over its nights; a night outside the window counts
  for nothing. A block is not scored until every stay touching it is settled.
- Analysis: mean of within-pair differences (treatment - control), with an
  exact sign-flip randomization test and a confidence interval by inverting it.
  Valid for any number of pairs and makes no normality assumption, which is the
  only defensible choice with three homes.
- Decision: PROVEN only if the portfolio interval excludes zero from above AND
  no home's and no owner's interval falls wholly below -margin; HARM if any
  interval lies wholly below -margin or a stop rule fired; else INCONCLUSIVE.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import numpy as np

from src.data_spine.ingest import current_rows
from src.data_spine.owner_net import effective_lines, owner_net_for_reservation

PLAN_FIELDS = ("plan_id", "properties", "owners", "start", "end", "block_days", "primary_metric",
               "portfolio_margin", "segment_margin", "alpha", "stop_rules", "comparator",
               "candidate_register", "analysis")


class PlanError(RuntimeError):
    pass


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def freeze_plan(plan: dict[str, Any], out: Path) -> dict[str, Any]:
    missing = [k for k in PLAN_FIELDS if k not in plan]
    if missing:
        raise PlanError(f"plan missing {missing}")
    if out.exists():
        raise PlanError(f"{out.name} is frozen; a change is a new plan_id")
    if set(plan["owners"]) != set(plan["properties"]):
        raise PlanError("every property needs an owner (segment harm is judged per owner)")
    if date.fromisoformat(plan["end"]) <= date.fromisoformat(plan["start"]):
        raise PlanError("end must be after start")
    if not 0 < float(plan["alpha"]) < 0.5:
        raise PlanError("alpha must be in (0, 0.5)")
    for name, beta in (plan.get("covariate_coefficients") or {}).items():
        if isinstance(beta, bool) or not isinstance(beta, (int, float)):
            raise PlanError(f"covariate {name} needs a numeric coefficient fitted on pre-period data")
    if "status_note" in plan:
        raise PlanError("remove the draft status_note before freezing")
    body = dict(plan)
    body["frozen_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body["plan_sha256"] = hashlib.sha256(_canonical({k: v for k, v in body.items() if k != "frozen_at"})).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    return body


def load_plan(path: Path) -> dict[str, Any]:
    body = json.loads(Path(path).read_text())
    check = hashlib.sha256(_canonical({k: v for k, v in body.items()
                                       if k not in ("frozen_at", "plan_sha256")})).hexdigest()
    if check != body.get("plan_sha256"):
        raise PlanError("plan content does not match its hash (edited after freeze)")
    return body


# -- assignment ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Block:
    property_id: str
    pair: int
    start: date
    end: date            # inclusive
    arm: str             # treatment | control


def blocks(plan: dict[str, Any]) -> list[Block]:
    """Deterministic, seeded from the frozen plan's hash; unpredictable before freezing."""
    if "plan_sha256" not in plan:
        raise PlanError("assignments exist only for a frozen plan")
    start, end, k = date.fromisoformat(plan["start"]), date.fromisoformat(plan["end"]), int(plan["block_days"])
    out: list[Block] = []
    for pid in sorted(plan["properties"]):
        pair, cur = 0, start
        while cur + timedelta(days=2 * k - 1) <= end:
            coin = hashlib.sha256(f"{plan['plan_sha256']}|{pid}|{pair}".encode()).digest()[0] & 1
            first, second = ("treatment", "control") if coin else ("control", "treatment")
            out.append(Block(pid, pair, cur, cur + timedelta(days=k - 1), first))
            out.append(Block(pid, pair, cur + timedelta(days=k), cur + timedelta(days=2 * k - 1), second))
            pair += 1
            cur += timedelta(days=2 * k)
    return out


def arm_for(plan: dict[str, Any]):
    index = {(b.property_id, b.start + timedelta(days=i)): b.arm
             for b in blocks(plan) for i in range((b.end - b.start).days + 1)}

    def lookup(property_id: str, stay_date: str | date) -> str:
        d = stay_date if isinstance(stay_date, date) else date.fromisoformat(str(stay_date)[:10])
        return index.get((property_id, d), "not_assigned")
    return lookup


# -- outcomes -----------------------------------------------------------------------------

@dataclass
class BlockOutcome:
    block: Block
    eligible_nights: int
    owner_net: float
    complete: bool
    pending: list[str] = field(default_factory=list)

    @property
    def per_night(self) -> float | None:
        return self.owner_net / self.eligible_nights if self.eligible_nights else None


_RESTRICTING = ("owner_block", "maintenance", "emergency")


def _restricted_days(conn: sqlite3.Connection) -> set[tuple[str, date]]:
    """Nights taken off the market by the owner or for maintenance (current constraints)."""
    out: set[tuple[str, date]] = set()
    for r in current_rows(conn, "dim_listing_constraint"):
        if r["active"] and r["constraint_type"] in _RESTRICTING:
            d, end = date.fromisoformat(r["start_date"]), date.fromisoformat(r["end_date"])
            while d <= end:
                out.add((r["property_id"], d))
                d += timedelta(days=1)
    return out


def block_outcomes(conn: sqlite3.Connection, plan: dict[str, Any]) -> list[BlockOutcome]:
    """Settled owner net per eligible night for every block. Reads the spine only."""
    nights_by_res: dict[str, list[date]] = {}
    res_rows = current_rows(conn, "fact_reservation_version")
    for r in res_rows:
        ci, co = date.fromisoformat(r["check_in"]), date.fromisoformat(r["check_out"])
        nights_by_res[r["entity_key"]] = [ci + timedelta(days=i) for i in range((co - ci).days)]
    prop_of = {r["entity_key"]: r["property_id"] for r in res_rows}
    restricted = _restricted_days(conn)
    out = []
    for b in blocks(plan):
        days = [b.start + timedelta(days=i) for i in range((b.end - b.start).days + 1)]
        eligible = [d for d in days if (b.property_id, d) not in restricted]
        total, pending = 0.0, []
        for key, nights in nights_by_res.items():
            if prop_of[key] != b.property_id or not nights:
                continue
            inside = [d for d in nights if d in eligible]
            if not inside:
                continue
            net = owner_net_for_reservation(conn, key)
            settled = _all_settled(conn, key)
            if net.status not in ("actual", "cancelled_no_money") or not settled:
                pending.append(key)
                continue
            total += net.total * len(inside) / len(nights)
        out.append(BlockOutcome(b, len(eligible), round(total, 2), complete=not pending, pending=pending))
    return out


def _all_settled(conn: sqlite3.Connection, reservation_key: str) -> bool:
    """Every line that counts toward owner net is settled (booking-time estimates replaced)."""
    return all(r["settlement_state"] == "settled" for r in effective_lines(conn, reservation_key))


# -- analysis -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Effect:
    n_pairs: int
    mean_diff: float              # owner net per eligible night, treatment - control
    lo: float
    hi: float
    p_value: float
    control_mean: float

    @property
    def relative(self) -> tuple[float, float, float] | None:
        if not self.control_mean:
            return None
        c = self.control_mean
        return (self.mean_diff / c, self.lo / c, self.hi / c)


def _signs(n: int, *, draws: int, seed: int) -> np.ndarray:
    """Every sign vector when that is small enough, else a fixed random sample of them.

    The observed assignment (all +1) is always included, so p is never 0.
    """
    if n <= 12:
        return np.array(list(itertools.product((1, -1), repeat=n)), dtype=float)
    rng = np.random.default_rng(seed)
    draws_ = rng.choice((1.0, -1.0), size=(draws - 1, n))
    return np.vstack([np.ones((1, n)), draws_])


def _p_value(diffs: list[float], shift: float, signs: np.ndarray) -> float:
    d = np.asarray(diffs, dtype=float) - shift
    obs = abs(d.sum())
    return float(np.mean(np.abs(signs @ d) >= obs - 1e-9))


def paired_effect(pairs: Iterable[tuple[float, float]], *, alpha: float = 0.10, draws: int = 4000,
                  seed: int = 20261016) -> Effect:
    """Sign-flip randomization test, and its inverted confidence interval, on (treatment, control).

    The interval is every shift whose test is not rejected at `alpha`; its ends are
    found by bisection (the p-value falls monotonically away from the mean).
    """
    pairs = list(pairs)
    if len(pairs) < 2:
        raise ValueError("need at least two complete pairs")
    diffs = [t - c for t, c in pairs]
    signs = _signs(len(diffs), draws=draws, seed=seed)
    m = mean(diffs)
    span = (max(diffs) - min(diffs)) or abs(m) or 1.0

    # The smallest p-value any shift can reach is the share of sign vectors tied
    # with the identity at the extreme; with too few pairs it exceeds alpha and
    # no shift is ever rejected, so the honest interval is unbounded.
    floor = float(np.mean(np.abs(signs.sum(axis=1)) == len(diffs)))
    if floor > alpha:
        return Effect(len(diffs), round(m, 4), float("-inf"), float("inf"),
                      round(_p_value(diffs, 0.0, signs), 5), round(mean(c for _, c in pairs), 4))

    def edge(direction: int) -> float:
        inside, outside = m, m + direction * span * 4
        for _ in range(60):                                # widen until rejected
            if _p_value(diffs, outside, signs) <= alpha:
                break
            outside += direction * span * 4
        for _ in range(40):
            mid = (inside + outside) / 2
            if _p_value(diffs, mid, signs) > alpha:
                inside = mid
            else:
                outside = mid
        return inside

    return Effect(len(diffs), round(m, 4), round(edge(-1), 4), round(edge(1), 4),
                  round(_p_value(diffs, 0.0, signs), 5), round(mean(c for _, c in pairs), 4))


def analyse(outcomes: list[BlockOutcome], plan: dict[str, Any],
            covariates: dict[tuple[str, date], dict[str, float]] | None = None,
            fired_stop_rules: list[str] | None = None) -> dict[str, Any]:
    """The preregistered decision. Incomplete pairs are reported and left out.

    Covariate adjustment (variance reduction): when the frozen plan carries
    `covariate_coefficients` {name: beta}, each pair's difference becomes
    (y_T - y_C) - sum(beta * (x_T - x_C)), with x per (home, block start) from
    `covariates`. The betas are fixed in the plan from pre-period data only, so
    the sign-flip test stays exact; a pair missing a covariate is left out.

    Segment harm is judged at alpha / k (Bonferroni over the k distinct segments;
    an owner with one home is the same segment as that home and is not counted
    twice). Any fired stop rule (`check_stop_rules`) makes the verdict HARM.
    """
    betas: dict[str, float] = {k: float(v) for k, v in (plan.get("covariate_coefficients") or {}).items()}
    if betas and covariates is None:
        raise PlanError("plan declares covariates; pass their values")
    by_pair: dict[tuple[str, int], dict[str, BlockOutcome]] = {}
    for o in outcomes:
        by_pair.setdefault((o.block.property_id, o.block.pair), {})[o.block.arm] = o
    complete, incomplete = [], []
    for key, arms in sorted(by_pair.items()):
        t, c = arms.get("treatment"), arms.get("control")
        if t and c and t.complete and c.complete and t.per_night is not None and c.per_night is not None:
            adj = 0.0
            if betas:
                xt = (covariates or {}).get((key[0], t.block.start), {})
                xc = (covariates or {}).get((key[0], c.block.start), {})
                if any(n not in xt or n not in xc for n in betas):
                    incomplete.append(f"{key[0]}#{key[1]} (covariate missing)")
                    continue
                adj = sum(b * (xt[n] - xc[n]) for n, b in betas.items())
            # The adjustment is applied to treatment only, so control means stay raw.
            # The guard above proves both optional properties are floats.
            assert t.per_night is not None and c.per_night is not None
            complete.append((key[0], t.per_night - adj, c.per_night))
        else:
            incomplete.append(f"{key[0]}#{key[1]}")
    alpha = float(plan["alpha"])
    result: dict[str, Any] = {"plan_id": plan["plan_id"], "plan_sha256": plan["plan_sha256"],
                              "complete_pairs": len(complete), "incomplete_pairs": incomplete,
                              "covariate_adjusted": sorted(betas)}
    if len(complete) < 2:
        result["decision"] = "INCONCLUSIVE"
        result["why"] = "fewer than two complete pairs"
        return result
    port = paired_effect([(t, c) for _, t, c in complete], alpha=alpha)
    result["portfolio"] = port.__dict__ | {"relative": port.relative}
    segments: dict[str, Any] = {}
    owners = plan["owners"]
    groups: dict[str, list[tuple[float, float]]] = {}
    homes_of: dict[str, set[str]] = {}
    for pid, treatment_value, control_value in complete:
        groups.setdefault(f"property:{pid}", []).append((treatment_value, control_value))
        homes_of.setdefault(owners[pid], set()).add(pid)
    for pid, treatment_value, control_value in complete:
        if len(homes_of[owners[pid]]) > 1:
            groups.setdefault(f"owner:{owners[pid]}", []).append((treatment_value, control_value))
    judged = [n for n, pr in groups.items() if len(pr) >= 2]
    seg_alpha = alpha / max(1, len(judged))
    harm, why = [], []
    for name, pr in sorted(groups.items()):
        if len(pr) < 2:
            segments[name] = {"n_pairs": len(pr), "note": "too few pairs to judge"}
            continue
        # Two intervals per segment. "Every segment is non-inferior" (needed for PROVEN) is
        # an intersection-union test and needs no multiplicity adjustment; "some segment is
        # harmed" is a union over k tests, so HARM uses alpha / k.
        eff = paired_effect(pr, alpha=alpha)
        harm_eff = paired_effect(pr, alpha=seg_alpha)
        rel, harm_rel = eff.relative, harm_eff.relative
        segments[name] = eff.__dict__ | {"relative": rel, "harm_interval_relative": harm_rel,
                                         "harm_alpha": round(seg_alpha, 4)}
        if harm_eff.lo == float("-inf"):
            # 2 / 2^n > alpha / k: no result could show harm. Say so, so "no HARM" is not
            # read as "no harm"; until enough pairs exist, the stop rules are the guard.
            segments[name]["harm_note"] = (f"{len(pr)} pairs cannot show harm at alpha {seg_alpha:.3f}; "
                                           "stop rules are the only guard")
        if harm_rel and harm_rel[2] < -float(plan["segment_margin"]):
            harm.append(name)
    result["segments"] = segments
    rel = port.relative
    if fired_stop_rules:
        result["decision"], why = "HARM", [f"stop rule fired: {r}" for r in fired_stop_rules]
    elif harm:
        result["decision"], why = "HARM", [f"interval wholly below -{plan['segment_margin']:.0%}: {harm}"]
    elif rel and rel[2] < -float(plan["portfolio_margin"]):
        result["decision"], why = "HARM", ["portfolio interval wholly below -margin"]
    elif port.lo > 0 and not any(
            isinstance(v, dict) and v.get("relative") and v["relative"][1] < -float(plan["segment_margin"])
            for v in segments.values()):
        result["decision"] = "PROVEN"
    else:
        result["decision"] = "INCONCLUSIVE"
        why = ["portfolio interval includes zero" if port.lo <= 0 else
               "a segment's interval reaches below -margin"]
    result["why"] = why
    return result


# -- stopping rules (leading indicators, checked during the test) --------------------------------

def check_stop_rules(conn: sqlite3.Connection, plan: dict[str, Any], *, as_of: date) -> list[str]:
    """Fired stop rules. Leading indicators, because settled money arrives months later.

    pickup_gap: for blocks still ahead, booked share of treatment nights trails the
        paired control nights by more than `max_pickup_gap` (absolute) for any home,
        once at least `min_nights` nights are compared.
    cancellation_rate: treatment-night cancellation share exceeds control's by more
        than `max_cancel_gap`.
    """
    rules = plan["stop_rules"]
    fired = []
    lookup = arm_for(plan)
    cal = current_rows(conn, "fact_calendar_observation")
    per: dict[tuple[str, str], list[int]] = {}
    for r in cal:
        arm = lookup(r["property_id"], r["stay_date"])
        if arm == "not_assigned" or r["status"] == "blocked" or r["stay_date"] <= as_of.isoformat():
            continue
        per.setdefault((r["property_id"], arm), []).append(int(r["status"] == "booked"))
    gap_cap = float(rules.get("max_pickup_gap", 0.15))
    min_n = int(rules.get("min_nights", 20))
    for pid in plan["properties"]:
        t, c = per.get((pid, "treatment"), []), per.get((pid, "control"), [])
        if len(t) >= min_n and len(c) >= min_n and mean(c) - mean(t) > gap_cap:
            fired.append(f"pickup_gap:{pid}: treatment {mean(t):.0%} vs control {mean(c):.0%}")
    res = current_rows(conn, "fact_reservation_version")
    cancel: dict[str, list[int]] = {"treatment": [], "control": []}
    for r in res:
        arm = lookup(r["property_id"], r["check_in"])
        if arm in cancel:
            cancel[arm].append(int(r["status"] == "cancelled"))
    cap = float(rules.get("max_cancel_gap", 0.10))
    if len(cancel["treatment"]) >= 5 and len(cancel["control"]) >= 5 and \
            mean(cancel["treatment"]) - mean(cancel["control"]) > cap:
        fired.append(f"cancellation_rate: treatment {mean(cancel['treatment']):.0%} vs control "
                     f"{mean(cancel['control']):.0%}")
    return fired
