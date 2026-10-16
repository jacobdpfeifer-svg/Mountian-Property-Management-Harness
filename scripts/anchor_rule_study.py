#!/usr/bin/env python3
"""Which competitor-anchor rule? A study with known ground truth plus a real-data replay.

    anchor_rule_study.py --db PATH [--trials 120] [--out docs/reports/anchor_rule_study]

Part 1 (measure): from the real comp_snapshots, how far a comp's quote for a
night drifts with age, how much the comps in one set differ, and the real
day-by-day share of each set that scraped successfully.

Part 2 (Monte Carlo): synthetic comp sets built from those measurements, scraped
through the *real* sequence of scraper-health days (circular block replay), so
outages are as long and as clustered as they really were. The true market
level is known, so every rule is scored against it:

    global_latest       the pre-2026-10-16 rule (one MAX(as_of) over all comps/homes)
    own_latest_date     latest scrape date with any good quote in this home's set
    per_comp(S, N)      each own comp's latest good quote no older than S days,
                        anchor only when at least N comps contribute

When a rule has no anchor the engine falls back to the home's own reference; that
fallback's error is unknown, so it is swept.

Part 3 (replay): the share of real (home, night, decision day) cells each rule
anchors, using the production comp_anchor for the per-comp rules.

Reads the database read-only. Writes REPORT.md and results.json.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import statistics as st
import sys
import zlib
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pricing.pace import comp_anchor  # noqa: E402

AGES = (3, 7, 14, 21, 28, 42, 60)
MINS = (1, 2, 3, 4)
FALLBACK_ERRORS = (0.10, 0.20, 0.30)


# -- part 1: measurements ---------------------------------------------------------------

def measure(conn: sqlite3.Connection) -> dict:
    ok = conn.execute(
        "SELECT comp_id, as_of, stay_date, listed_price FROM comp_snapshots "
        "WHERE scrape_status='ok' AND listed_price > 0").fetchall()
    by = defaultdict(list)
    for comp, as_of, stay, price in ok:
        by[(comp, stay)].append((date.fromisoformat(as_of[:10]), float(price)))
    drift = defaultdict(list)
    for quotes in by.values():
        quotes.sort()
        for i, (d1, p1) in enumerate(quotes):
            for d2, p2 in quotes[i + 1:]:
                g = (d2 - d1).days
                if 0 < g <= 21:
                    drift[g].append(abs(math.log(p2 / p1)))
    members = defaultdict(set)
    for pid, comp in conn.execute("SELECT property_id, comp_id FROM comp_set_members"):
        members[pid].add(comp)
    cells = defaultdict(list)
    for comp, as_of, stay, price in ok:
        cells[(as_of[:10], stay)].append((comp, math.log(float(price))))
    spread = {}
    for pid, m in members.items():
        sds = [st.pstdev([x for c, x in v if c in m]) for v in cells.values()
               if sum(c in m for c, _ in v) >= 3]
        spread[pid] = {"cells": len(sds), "median_sd_log": round(st.median(sds), 3) if sds else None}
    # Real scraper health: per home and scrape day, the share of its comps with any good quote.
    days = [r[0] for r in conn.execute("SELECT DISTINCT substr(as_of,1,10) FROM comp_snapshots ORDER BY 1")]
    health = {}
    for pid, m in members.items():
        seq = []
        for d in days:
            n = conn.execute(
                f"SELECT COUNT(DISTINCT comp_id) FROM comp_snapshots WHERE substr(as_of,1,10)=? "
                f"AND scrape_status='ok' AND listed_price>0 AND comp_id IN ({','.join('?' * len(m))})",
                (d, *sorted(m))).fetchone()[0]
            seq.append(round(n / len(m), 3))
        health[pid] = {"days": days, "ok_share": seq}
    return {
        "drift": {g: {"n": len(v), "mean_abs_log": round(st.mean(v), 4),
                      "median_abs_log": round(st.median(v), 4)} for g, v in sorted(drift.items())},
        "spread": spread,
        "health": health,
        "members": {p: sorted(m) for p, m in members.items()},
    }


# -- part 2: Monte Carlo -----------------------------------------------------------------

def _median(xs: list[float]) -> float:
    return st.median(xs)


def repeat_sales_index(obs_by_day: list[list[tuple[tuple, float]]]) -> list[float]:
    """Market log-price index from repeat quotes of the same (comp, night).

    Day t's level is the median over every (comp, night) quoted on t of
    (log quote - its previous log quote + index on that previous day). A day with
    no repeat quote keeps the previous level. This is the BLS "cell-relative"
    idea: a comp missing today is moved by the change seen in comps observed.
    """
    index: list[float] = []
    last: dict[tuple, tuple[int, float]] = {}
    for t, quotes in enumerate(obs_by_day):
        moves = [x - prev_x + index[prev_t] for key, x in quotes
                 for prev_t, prev_x in [last.get(key, (None, None))]
                 if prev_t is not None and prev_x is not None]
        index.append(_median(moves) if moves else (index[-1] if index else 0.0))
        for key, x in quotes:
            last[key] = (t, x)
    return index


def simulate(health_seq: list[float], n_comps: int, sd_comp: float, *, trials: int, seed: int,
             idio_prob: float, idio_sd: float, common_prob: float, common_mu: float,
             common_sd: float, booking: bool, night_scrape_share: float = 0.6,
             outlier_rate: float = 0.0, wave_prob: float = 0.0, wave_share: float = 0.5,
             wave_mu: float = -0.08, wave_sd: float = 0.04) -> dict:
    """Score every rule against the true market median (log-scale absolute error).

    True log ask = night level + comp level + comp-night idiosyncratic jumps, plus
    two kinds of market move: a common factor shared by every comp and night, and
    partial waves (on a wave day each comp, with probability `wave_share`, cuts its
    whole calendar). The real Sep-Oct 2026 scrapes show partial waves: about half
    the comps dropped ~5-10% while the rest held, so an index of the others' moves
    predicted a comp's next quote worse than its own old quote (see `holdout`).
    A comp that sells the night stops moving. Scrapes follow the real health
    sequence; a comp reached that day is quoted on `night_scrape_share` of nights.
    `outlier_rate` corrupts that share of good quotes (x0.3 or x3: placeholders, parse slips).
    """
    rng = random.Random(seed)
    n_days, n_nights = 45, 30
    rules = (["global_latest", "own_latest_date"] + [f"per_comp({s},{n})" for s in AGES for n in MINS]
             + [f"imputed({s},{n})" for s in AGES for n in MINS])
    err: dict[str, list[float]] = {r: [] for r in rules}
    miss = {r: 0 for r in rules}
    total = 0
    L = len(health_seq)
    for _ in range(trials):
        start = rng.randrange(L)
        level = [rng.gauss(0, sd_comp) for _ in range(n_comps)]
        nights = rng.sample(range(10, 90 + n_days), n_nights)
        night_mu = {n: rng.gauss(0, 0.15) for n in nights}
        idio = {(c, n): 0.0 for c in range(n_comps) for n in nights}
        booked: set[tuple[int, int]] = set()
        frozen: dict[tuple[int, int], float] = {}
        factor = 0.0
        comp_shift = [0.0] * n_comps
        obs_by_day: list[list[tuple[tuple, float]]] = []
        last_ok: dict[tuple[int, int], tuple[int, float]] = {}
        for day in range(n_days):
            if rng.random() < common_prob:
                factor += rng.gauss(common_mu, common_sd)
            if rng.random() < wave_prob:
                for c in range(n_comps):
                    if rng.random() < wave_share:
                        comp_shift[c] += rng.gauss(wave_mu, wave_sd)
            truth_px: dict[int, list[float]] = {}
            quotes_today: list[tuple[tuple, float]] = []
            h = health_seq[(start + day) % L]
            reached = [rng.random() < h for _ in range(n_comps)]
            for n in nights:
                if n <= day:
                    continue
                lead = n - day
                for c in range(n_comps):
                    key = (c, n)
                    if key not in booked:
                        if rng.random() < idio_prob:
                            idio[key] += rng.gauss(0, idio_sd)
                        if booking and rng.random() < 0.012 * (1 + (90 - min(lead, 90)) / 30):
                            booked.add(key)
                            frozen[key] = night_mu[n] + level[c] + idio[key] + factor + comp_shift[c]
                    px = frozen.get(key, night_mu[n] + level[c] + idio[key] + factor + comp_shift[c])
                    truth_px.setdefault(n, []).append(px)
                    if reached[c] and key not in booked and rng.random() < night_scrape_share:
                        q = px
                        if outlier_rate and rng.random() < outlier_rate:
                            q += math.log(rng.choice((0.3, 3.0)))
                        quotes_today.append((key, q))
                        last_ok[key] = (day, q)
            obs_by_day.append(quotes_today)
            index = repeat_sales_index(obs_by_day)
            if day < 3:
                continue
            for n, prices in truth_px.items():
                truth = _median(prices)
                total += 1
                g = [q for (c, nn), q in quotes_today if nn == n]
                _score(err, miss, "global_latest", g, truth)
                own = [(last_ok[(c, n)]) for c in range(n_comps) if (c, n) in last_ok]
                latest = max((d for d, _ in own), default=None)
                _score(err, miss, "own_latest_date",
                       [] if latest is None else [x for d, x in own if d == latest], truth)
                for s_age in AGES:
                    fresh = [(d, x) for d, x in own if day - d <= s_age]
                    carried = [x for _, x in fresh]
                    imputed = [x + index[day] - index[d] for d, x in fresh]
                    for n_min in MINS:
                        ok = len(fresh) >= n_min
                        _score(err, miss, f"per_comp({s_age},{n_min})", carried if ok else [], truth)
                        _score(err, miss, f"imputed({s_age},{n_min})", imputed if ok else [], truth)
    out: dict[str, Any] = {}
    for r in rules:
        e = err[r]
        row = {"available": round(1 - miss[r] / total, 3),
               "median_abs_err": round(st.median(e), 4) if e else None,
               "p90_abs_err": round(sorted(e)[int(0.9 * len(e))], 4) if e else None,
               "bias": None}
        for fb in FALLBACK_ERRORS:
            row[f"loss_fb{int(fb * 100)}"] = round((sum(e) + fb * miss[r]) / total, 4)
        out[r] = row
    return out


def _score(err: dict, miss: dict, rule: str, quotes: list[float], truth: float) -> None:
    if quotes:
        err[rule].append(abs(_median(quotes) - truth))
    else:
        miss[rule] += 1


def holdout(conn: sqlite3.Connection) -> dict:
    """Real check: predict a comp's actual quote today from its own older quote.

    For every good quote (comp, night, day t) with an earlier good quote of the
    same comp and night at t' < t, compare carry-forward (the old quote) with the
    old quote moved by the home's repeat-sales index from t' to t, where the
    index on t is built only from *other* comps (leave-one-comp-out, no peeking).
    """
    rows = conn.execute(
        "SELECT m.property_id, s.comp_id, substr(s.as_of,1,10), s.stay_date, s.listed_price "
        "FROM comp_snapshots s JOIN comp_set_members m ON m.comp_id = s.comp_id "
        "WHERE s.scrape_status='ok' AND s.listed_price > 0 AND s.as_of >= '2026-09-20'").fetchall()
    by_home = defaultdict(list)
    for pid, comp, day, stay, price in rows:
        by_home[pid].append((comp, date.fromisoformat(day), stay, math.log(float(price))))
    out = {}
    for pid, quotes in by_home.items():
        days = sorted({d for _, d, _, _ in quotes})
        pos = {d: i for i, d in enumerate(days)}
        comps = sorted({c for c, _, _, _ in quotes})
        res: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"carry": [], "imputed": []})
        for held in comps:
            obs: list[list[tuple[tuple[Any, ...], float]]] = [[] for _ in days]
            for c, d, stay, x in quotes:
                if c != held:
                    obs[pos[d]].append(((c, stay), x))
            idx = repeat_sales_index(obs)
            mine = sorted((d, stay, x) for c, d, stay, x in quotes if c == held)
            prev: dict[str, tuple[date, float]] = {}
            for d, stay, x in mine:
                if stay in prev:
                    d0, x0 = prev[stay]
                    gap = (d - d0).days
                    bucket = "1-3" if gap <= 3 else "4-7" if gap <= 7 else "8-14" if gap <= 14 else "15+"
                    res[bucket]["carry"].append(abs(x - x0))
                    res[bucket]["imputed"].append(abs(x - (x0 + idx[pos[d]] - idx[pos[d0]])))
                prev[stay] = (d, x)
        out[pid] = {b: {"n": len(v["carry"]), "carry_mae": round(st.mean(v["carry"]), 4),
                        "imputed_mae": round(st.mean(v["imputed"]), 4)}
                    for b, v in sorted(res.items()) if v["carry"]}
    return out


# -- part 3: real replay ---------------------------------------------------------------

def replay(conn: sqlite3.Connection) -> dict:
    conn.row_factory = sqlite3.Row
    days = [date.fromisoformat(r[0]) for r in conn.execute(
        "SELECT DISTINCT substr(as_of,1,10) FROM comp_snapshots WHERE as_of >= '2026-09-20' ORDER BY 1")]
    stays = [date.fromisoformat(r[0]) for r in conn.execute(
        "SELECT DISTINCT stay_date FROM comp_snapshots WHERE stay_date IS NOT NULL ORDER BY 1")]
    homes = [r[0] for r in conn.execute("SELECT DISTINCT property_id FROM comp_set_members ORDER BY 1")]
    rows: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    last_day: dict[tuple[str, str], list[int]] = {}
    for pid in homes:
        for d in days:
            for stay in stays:
                if not (d < stay <= d + timedelta(days=120)):
                    continue
                old = _old_rule(conn, pid, stay, d)
                anchors: list[tuple[str, int]] = [("global_latest", old)]
                for age in (14, 28, 42):
                    _, quote_count = comp_anchor(conn, pid, stay, d, max_age_days=age)
                    for minimum in (1, 3):
                        anchors.append((f"per_comp({age},{minimum})",
                                        quote_count if quote_count >= minimum else 0))
                for name, n in anchors:
                    rows[(pid, name)][1] += 1
                    rows[(pid, name)][0] += 1 if n else 0
                    if d == days[-1]:
                        last_day.setdefault((pid, name), [0, 0])
                        last_day[(pid, name)][1] += 1
                        last_day[(pid, name)][0] += 1 if n else 0
    return {
        "window": [days[0].isoformat(), days[-1].isoformat()],
        "anchored_share": {f"{p}|{r}": round(a / t, 3) for (p, r), (a, t) in sorted(rows.items())},
        "anchored_share_on_last_day": {f"{p}|{r}": round(a / t, 3) for (p, r), (a, t) in sorted(last_day.items())},
    }


def _old_rule(conn: sqlite3.Connection, pid: str, stay: date, as_of: date) -> int:
    return conn.execute(
        """SELECT COUNT(*) FROM comp_snapshots s
           JOIN comp_set_members m ON m.comp_id = s.comp_id AND m.property_id = ?
           WHERE s.stay_date = ? AND s.scrape_status = 'ok' AND s.listed_price > 0
             AND s.as_of = (SELECT MAX(as_of) FROM comp_snapshots WHERE stay_date = ? AND as_of <= ?)""",
        (pid, stay.isoformat(), stay.isoformat(), as_of.isoformat())).fetchone()[0]


# -- report --------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--trials", type=int, default=120)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "reports" / "anchor_rule_study")
    a = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    m = measure(conn)
    # Health replay from 2026-09-20 on: the 09-01 seed scrape was a one-off curation sweep.
    first = m["health"][next(iter(m["health"]))]["days"].index("2026-09-20")
    worlds = {}
    homes = sorted(m["health"])
    # Fitted to the real drift curve (mean abs log change of a comp's quote for a
    # night, by age): 0.5/1.0/1.5/2.4/3.3/4.6/6.3/8.1/9.5% at 1/2/3/5/7/10/14/18/21
    # days vs real 0.8/0.9/1.6/2.7/5.0/2.9/4.4/8.5/9.4%. It overstates 10-14 days,
    # which penalises long age caps, not short ones. The common-shift world is the stress case
    # where imputation should win; the real holdout says it is not what happened.
    none: dict[str, Any] = {"common_prob": 0.0, "common_mu": 0.0, "common_sd": 0.0}
    waves = {**none, "wave_prob": 0.08, "wave_share": 0.5, "wave_mu": -0.10, "wave_sd": 0.04}
    common = {"common_prob": 0.15, "common_mu": -0.025, "common_sd": 0.025}
    for pid in homes:
        seq = m["health"][pid]["ok_share"][first:]
        n = len(m["members"][pid])
        for sd in (0.22, 0.42):
            for label, kw in (("partial_waves", {**waves, "booking": True}),
                              ("partial_waves+outliers", {**waves, "booking": True, "outlier_rate": 0.03}),
                              ("common_shift", {**common, "booking": True}),
                              ("quiet_market", {**none, "booking": True})):
                key = f"{pid}|n={n}|sd={sd}|{label}"
                worlds[key] = simulate(seq, n, sd, trials=a.trials, seed=zlib.crc32(key.encode()),
                                       idio_prob=0.04, idio_sd=0.03, **kw)
    worlds["sim_v2_scrape|n=7|sd=0.22|partial_waves"] = simulate(
        [0.92] * 26, 7, 0.22, trials=a.trials, seed=7, idio_prob=0.04, idio_sd=0.03, booking=True, **waves)
    rp = replay(conn)
    ho = holdout(conn)
    a.out.mkdir(parents=True, exist_ok=True)
    # Comp ids name real listings (some are confidential Cloud 9 comps): counts only.
    measured = {k: v for k, v in m.items() if k not in ("health", "members")}
    measured["comp_set_sizes"] = {p: len(v) for p, v in m["members"].items()}
    body = {"measurements": measured,
            # Per-day scrape health stays local: Cloud 9 evaluation data is confidential.
            "trials_per_world": a.trials,
            "monte_carlo": worlds, "replay": rp, "holdout": ho}
    (a.out / "results.json").write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    _report(a.out / "REPORT.md", body)
    print(f"wrote {a.out}/REPORT.md")
    return 0


def _rank(world: dict, fb: str) -> list[tuple[str, float]]:
    return sorted(((r, v[fb]) for r, v in world.items()), key=lambda x: x[1])


def _report(path: Path, body: dict) -> None:
    lines = ["# Competitor anchor rule study", "",
             "Generated by `scripts/anchor_rule_study.py`. Errors are absolute log errors "
             "(0.05 ≈ 5%) against the true market median.", "", "## Measured on the real scrapes", "",
             "| gap (days) | pairs | mean abs log drift |", "|---|---|---|"]
    for g, v in body["measurements"]["drift"].items():
        lines.append(f"| {g} | {v['n']} | {v['mean_abs_log']} |")
    lines += ["", "Cross-comp spread within a set (median SD of log price, cells with ≥3 comps): " +
              ", ".join(f"{p} {v['median_sd_log']} ({v['cells']} cells)"
                        for p, v in body["measurements"]["spread"].items()), ""]
    lines += ["## Monte Carlo: best rules per world", "",
              "Loss = expected abs log error per decision, charging the fallback's error on cells "
              "with no anchor.", ""]
    for key, world in body["monte_carlo"].items():
        lines += [f"### {key}", "", "| rule | anchored | median err | p90 err | loss fb=0.10 | fb=0.20 | fb=0.30 |",
                  "|---|---|---|---|---|---|---|"]
        top = ({r for r, _ in _rank(world, "loss_fb20")[:6]}
               | {r for r, _ in _rank({k: v for k, v in world.items() if k.startswith("per_comp")}, "loss_fb20")[:3]}
               | {"global_latest", "own_latest_date", "per_comp(14,3)", "imputed(14,3)", "imputed(28,3)"})
        for r in sorted(top, key=lambda r: world[r]["loss_fb20"]):
            v = world[r]
            lines.append(f"| {r} | {v['available']} | {v['median_abs_err']} | {v['p90_abs_err']} | "
                         f"{v['loss_fb10']} | {v['loss_fb20']} | {v['loss_fb30']} |")
        lines.append("")
    lines += ["## Real holdout: predicting a comp's actual quote from its older quote", "",
              "Mean abs log error. `imputed` moves the old quote by the repeat-sales index built "
              "from the other comps only.", "", "| home | gap (days) | n | carry-forward | imputed |",
              "|---|---|---|---|---|"]
    for pid, buckets in body["holdout"].items():
        for b, v in buckets.items():
            lines.append(f"| {pid} | {b} | {v['n']} | {v['carry_mae']} | {v['imputed_mae']} |")
    lines += ["", "## Real replay: share of (home, night, decision day) cells anchored", "",
              f"Window {body['replay']['window'][0]} to {body['replay']['window'][1]}.", "",
              "| home | rule | all days | last day |", "|---|---|---|---|"]
    for k, v in body["replay"]["anchored_share"].items():
        p, r = k.split("|")
        lines.append(f"| {p} | {r} | {v} | {body['replay']['anchored_share_on_last_day'].get(k)} |")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
