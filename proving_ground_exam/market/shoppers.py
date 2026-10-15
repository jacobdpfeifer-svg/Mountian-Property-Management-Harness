"""Shopper draws. The random stream does not depend on prices or availability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from proving_ground_exam.market.parameters import LEAD_BUCKETS, LOS_VALUES, season_of, seasonal, value_of
from proving_ground_exam.market.rngutil import generator


@dataclass
class Shopper:
    shopper_id: str
    segment: str
    check_in: date
    los: int
    party: int
    channel: str
    wtp_multiplier: float
    price_coef: float
    gumbels: dict[str, float]
    convert_u: float
    decision_day: date


def _holiday_boost(day: date, holidays: list[tuple[date, date]], multiplier: float, sensitive: bool) -> float:
    if not sensitive:
        return 1.0
    for start, end in holidays:
        if start - timedelta(days=60) <= day <= end:
            return multiplier
    return 1.0


def _modulator(weights: dict[str, float], snow: float, access: float, macro: float) -> float:
    factor = 1.0
    factor += float(weights["snow"]) * (snow - 0.5) * 2.0
    factor += float(weights["access"]) * (access - 0.5) * 2.0
    factor += float(weights["macro"]) * (macro - 0.5) * 2.0
    return float(min(3.0, max(0.05, factor)))


def draw_shoppers(
    cal: dict,
    *,
    scenario: str,
    seed: int,
    day: date,
    snow: float,
    access: float,
    macro: float,
    den_capacity: float,
    pandemic_factor: float,
    holidays: list[tuple[date, date]],
    alternative_ids: list[str],
) -> list[Shopper]:
    """Draw the day's shoppers. Alternative ids must be a stable sorted list."""
    rng = generator(scenario, seed, "shoppers", day.isoformat())
    season = season_of(day)
    holiday_mult = value_of(cal["holiday_multiplier"])
    sigma = value_of(cal["mixed_logit_sigma"])
    out: list[Shopper] = []
    for name in sorted(cal["segments"]):
        seg = cal["segments"][name]
        share = float(seg["share"][season])
        mean = value_of(cal["arrival_mean"]) * share
        mean *= _modulator(seasonal(seg["weights"], season), snow, access, macro)
        mean *= _holiday_boost(day, holidays, holiday_mult, bool(seg.get("holiday_sensitive")))
        mean *= pandemic_factor
        if name == "international":
            mean *= den_capacity
        count = int(rng.poisson(max(mean, 0.0)))
        # v2 segments may give lead, LOS, party, channel and weights per season
        # (the shopping day's season, like share). v1 values pass through.
        lead_p = np.asarray(seasonal(seg["lead"], season), dtype=float)
        lead_p = lead_p / lead_p.sum()
        los_p = np.asarray(seasonal(seg["los"], season), dtype=float)
        los_p = los_p / max(los_p.sum(), 1e-9)
        party_spec = seasonal(seg["party"], season)
        channel_spec = seasonal(seg["channel"], season)
        channels = list(channel_spec)
        channel_p = np.asarray([channel_spec[c] for c in channels], dtype=float)
        channel_p = channel_p / channel_p.sum()
        for i in range(count):
            bucket = int(rng.choice(len(LEAD_BUCKETS), p=lead_p))
            lo, hi = LEAD_BUCKETS[bucket]
            lead = int(rng.integers(lo, hi + 1))
            los = int(rng.choice(np.asarray(LOS_VALUES), p=los_p))
            party = int(round(float(rng.triangular(party_spec["low"], party_spec["mode"], party_spec["high"]))))
            party = int(min(party_spec["high"], max(party_spec["low"], party)))
            channel = str(rng.choice(np.asarray(channels), p=channel_p))
            z_w = float(rng.normal())
            # Willingness to pay belongs to the stay, so v2 reads it by the
            # check-in season (spec: families 1.20 peak / 1.10 early / 1.05 shoulder).
            wtp_median = seasonal(seg["wtp"]["median"], season_of(day + timedelta(days=lead)))
            wtp = float(wtp_median) * float(np.exp(float(seg["wtp"]["sigma"]) * z_w))
            z_b = float(rng.normal())
            coef = float(seg["price_coef"][season]) * float(np.exp(sigma * z_b))
            coef = float(min(-0.05, coef))
            gumbels = {alt: float(-np.log(-np.log(min(1 - 1e-12, max(1e-12, rng.random()))))) for alt in alternative_ids}
            convert_u = float(rng.random())
            out.append(
                Shopper(
                    shopper_id=f"{day.isoformat()}:{name}:{i}",
                    segment=name,
                    check_in=day + timedelta(days=lead),
                    los=los,
                    party=party,
                    channel=channel,
                    wtp_multiplier=wtp,
                    price_coef=coef,
                    gumbels=gumbels,
                    convert_u=convert_u,
                    decision_day=day,
                )
            )
    return out
