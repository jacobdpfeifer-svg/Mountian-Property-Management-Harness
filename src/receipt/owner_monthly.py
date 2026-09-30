"""Monthly owner receipt: net performance, revenue decisions, property care, exceptions.

Money rules (stated on the receipt too):
  * Booking revenue, cleaning fees, and channel cost are pro-rated by nights
    that fall in the month. Owner stays are excluded from revenue.
  * Channel cost is derived: accommodation fare + cleaning fee - host payout.
    Stays missing any of the three are counted and reported, not guessed.
  * Service cost uses imported task costs where they exist and profile
    estimates for turns without one; the two are shown separately.
  * Management fee needs owners.<id>.management_fee_pct; otherwise the net is
    shown before the fee and says so.
Trust-account reconciliation is deliberately out of scope (docs/rules/OPERATIONS.md).
"""

from __future__ import annotations

import html
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.config import load_portfolio_config
from src.db import connect

SERVICE_TYPES = ("turnover", "spa", "snow", "inspection", "laundry")
MOVE_DOLLARS = 100.0


class PlaceholderOwnerName(RuntimeError):
    """The owner's name in config is still a placeholder."""


@dataclass
class PropertyMonth:
    property_id: str
    display_name: str
    nights_sold: int = 0
    gross_accommodation: float = 0.0
    cleaning_fees: float = 0.0
    channel_cost: float = 0.0
    channel_cost_missing: int = 0
    service_observed: float = 0.0
    service_estimated: float = 0.0
    turns_observed: int = 0
    turns_estimated: int = 0
    qa_checked: int = 0
    qa_passed: int = 0
    ledger: dict[str, float] = field(default_factory=dict)


@dataclass
class OwnerMonth:
    owner_id: str
    owner_name: str
    month_start: date
    month_end: date
    fee_pct: float | None
    properties: list[PropertyMonth]
    decisions: list[dict[str, Any]]
    applied_changes: int
    incidents: list[dict[str, Any]]
    asset_events: dict[str, int]
    readiness: list[dict[str, Any]]
    compliance: list[dict[str, Any]]
    owner_ledger: dict[str, float] = field(default_factory=dict)

    @property
    def gross(self) -> float:
        return sum(p.gross_accommodation + p.cleaning_fees for p in self.properties)

    @property
    def costs(self) -> dict[str, float]:
        ledger: dict[str, float] = dict(self.owner_ledger)
        for p in self.properties:
            for k, v in p.ledger.items():
                ledger[k] = ledger.get(k, 0.0) + v
        return {
            "channel": sum(p.channel_cost for p in self.properties),
            "service_observed": sum(p.service_observed for p in self.properties),
            "service_estimated": sum(p.service_estimated for p in self.properties),
            **{f"ledger_{k}": v for k, v in ledger.items()},
        }

    @property
    def management_fee(self) -> float | None:
        if self.fee_pct is None:
            return None
        return sum(p.gross_accommodation for p in self.properties) * self.fee_pct

    @property
    def net(self) -> float:
        return self.gross - sum(self.costs.values()) - (self.management_fee or 0.0)


def month_bounds(month: str) -> tuple[date, date]:
    start = date.fromisoformat(f"{month}-01")
    nxt = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, nxt - timedelta(days=1)


def _overlap(ci: date, co: date, start: date, end: date) -> int:
    return max(0, (min(co, end + timedelta(days=1)) - max(ci, start)).days)


def load_owner_month(conn: sqlite3.Connection, owner_id: str, month: str,
                     *, allow_placeholder_names: bool = False) -> OwnerMonth:
    from src.ops.db import ensure_ops_tables
    from src.ops.profiles import load_ops_policy, load_profiles
    from src.ops.economics import turn_cost
    from src.ops.turns import derive_turns

    ensure_ops_tables(conn)
    cfg = load_portfolio_config()
    owner = (cfg.get("owners") or {}).get(owner_id)
    if owner is None:
        raise LookupError(f"unknown owner {owner_id!r}")
    name = str(owner.get("name") or owner_id)
    if name.lower().endswith(" owner") and not allow_placeholder_names:
        raise PlaceholderOwnerName(
            f"owner name {name!r} is a placeholder in config/portfolio/mont_luxe.yaml; "
            "set the real name or pass --allow-placeholder-names for an internal draft")
    fee = owner.get("management_fee_pct")
    start, end = month_bounds(month)
    pids = list(owner.get("properties") or [])
    names = {pid: str((cfg.get("properties") or {}).get(pid, {}).get("display_name") or pid) for pid in pids}
    profiles = load_profiles()
    ops_policy = load_ops_policy()
    rows: list[PropertyMonth] = []
    for pid in pids:
        pm = PropertyMonth(pid, names[pid])
        for r in conn.execute(
            """SELECT check_in, check_out, fare_accommodation, fare_cleaning, host_payout, source
               FROM reservations WHERE property_id=?
                 AND LOWER(status) IN ('confirmed','checked_in','checked_out')
                 AND check_in<=? AND check_out>?""",
            (pid, end.isoformat(), start.isoformat()),
        ).fetchall():
            if (r["source"] or "").lower() == "owner":
                continue
            ci, co = date.fromisoformat(str(r["check_in"])[:10]), date.fromisoformat(str(r["check_out"])[:10])
            nights = max(1, (co - ci).days)
            share = _overlap(ci, co, start, end) / nights
            if share <= 0:
                continue
            pm.nights_sold += _overlap(ci, co, start, end)
            fare = float(r["fare_accommodation"] or 0.0)
            clean = float(r["fare_cleaning"] or 0.0)
            pm.gross_accommodation += fare * share
            pm.cleaning_fees += clean * share
            if r["fare_accommodation"] is not None and r["host_payout"] is not None:
                pm.channel_cost += max(0.0, fare + clean - float(r["host_payout"])) * share
            else:
                pm.channel_cost_missing += 1
        observed_dates: set[str] = set()
        for r in conn.execute(
            f"""SELECT service_date, service_type, cost, qa_pass FROM turnover_outcomes
                WHERE property_id=? AND service_date>=? AND service_date<=?
                  AND service_type IN ({','.join('?' * len(SERVICE_TYPES))})""",
            (pid, start.isoformat(), end.isoformat(), *SERVICE_TYPES),
        ).fetchall():
            if r["cost"] is not None:
                pm.service_observed += float(r["cost"])
            if r["service_type"] == "turnover":
                pm.turns_observed += 1
                observed_dates.add(str(r["service_date"])[:10])
            if r["qa_pass"] is not None:
                pm.qa_checked += 1
                pm.qa_passed += int(r["qa_pass"])
        profile = profiles.get(pid)
        if profile is not None:
            for t in derive_turns(conn, profile, start, end, as_of=end + timedelta(days=1),
                                  ops_policy=ops_policy):
                if t.service_date.isoformat() in observed_dates:
                    continue
                pm.turns_estimated += 1
                pm.service_estimated += turn_cost(conn, profile, as_of=end + timedelta(days=1),
                                                  ops_policy=ops_policy, snow=t.snow_expected).amount
        for r in conn.execute(
            """SELECT category, SUM(amount) AS total FROM owner_ledger_entries
               WHERE owner_id=? AND property_id=? AND entry_date>=? AND entry_date<=?
               GROUP BY category""",
            (owner_id, pid, start.isoformat(), end.isoformat()),
        ).fetchall():
            pm.ledger[str(r["category"])] = float(r["total"] or 0.0)
        rows.append(pm)

    owner_ledger = {str(r["category"]): float(r["total"] or 0.0) for r in conn.execute(
        """SELECT category, SUM(amount) AS total FROM owner_ledger_entries
           WHERE owner_id=? AND property_id IS NULL AND entry_date>=? AND entry_date<=?
           GROUP BY category""",
        (owner_id, start.isoformat(), end.isoformat()),
    ).fetchall()}
    placeholders = ",".join("?" * len(pids)) or "''"
    decisions = [dict(r) for r in conn.execute(
        f"""SELECT p.property_id, p.stay_date, p.listed_price_at_run, p.recommended_price,
                   p.recommended_min_stay, p.min_stay_source, p.status, p.autonomy_level
            FROM price_recommendations p
            JOIN (SELECT property_id, stay_date, MAX(id) AS id FROM price_recommendations
                  WHERE property_id IN ({placeholders}) AND stay_date>=? AND stay_date<=?
                  GROUP BY property_id, stay_date) l ON l.id=p.id
            WHERE p.status='blocked' OR (p.listed_price_at_run IS NOT NULL
                  AND ABS(p.recommended_price - p.listed_price_at_run) >= ?)
            ORDER BY ABS(p.recommended_price - COALESCE(p.listed_price_at_run, p.recommended_price)) DESC
            LIMIT 8""",
        (*pids, start.isoformat(), end.isoformat(), MOVE_DOLLARS),
    ).fetchall()]
    applied = conn.execute(
        f"""SELECT COUNT(*) AS c FROM rate_changes WHERE result='applied'
            AND property_id IN ({placeholders}) AND stay_date>=? AND stay_date<=?""",
        (*pids, start.isoformat(), end.isoformat()),
    ).fetchone()["c"]
    incidents = []
    for r in conn.execute(
        "SELECT * FROM incidents WHERE window_start<=? AND window_end>=? ORDER BY window_start",
        (end.isoformat(), start.isoformat()),
    ).fetchall():
        affected = json.loads(r["affected_json"] or "{}")
        if set(affected.get("properties", [])) & set(pids):
            incidents.append({"incident_id": r["incident_id"], "type": r["incident_type"],
                              "window": f"{r['window_start']}..{r['window_end']}", "status": r["status"]})
    events = conn.execute(
        f"""SELECT SUM(CASE WHEN observed_at<=? AND observed_at>=? THEN 1 ELSE 0 END) AS opened,
                   SUM(CASE WHEN resolved_at IS NOT NULL AND substr(resolved_at,1,10)>=?
                            AND substr(resolved_at,1,10)<=? THEN 1 ELSE 0 END) AS resolved,
                   SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS still_open
            FROM asset_health_events WHERE property_id IN ({placeholders})""",
        (f"{end.isoformat()}T23:59:59", start.isoformat(), start.isoformat(), end.isoformat(), *pids),
    ).fetchone()
    readiness = [dict(r) for r in conn.execute(
        f"""SELECT property_id, from_state, to_state, at, actor, note FROM readiness_transitions
            WHERE property_id IN ({placeholders}) AND substr(at,1,10)>=? AND substr(at,1,10)<=?
            ORDER BY at""",
        (*pids, start.isoformat(), end.isoformat()),
    ).fetchall()]
    from src.compliance import check

    comp = [r.as_dict() for r in check(conn, end, property_ids=pids).results
            if r.status in ("missing", "expired", "expiring") and not r.optional]
    return OwnerMonth(owner_id, name, start, end, float(fee) if fee is not None else None, rows,
                      decisions, int(applied or 0), incidents,
                      {k: int(events[k] or 0) for k in ("opened", "resolved", "still_open")},
                      readiness, comp, owner_ledger)


def _e(v: object) -> str:
    return html.escape(str(v), quote=True)


def _m(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "−" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}"


def render(om: OwnerMonth) -> str:
    c = om.costs
    fee_line = (f"<tr><td>Management fee ({om.fee_pct:.0%} of booking revenue)</td>"
                f"<td class=n>{_m(-(om.management_fee or 0))}</td></tr>"
                if om.fee_pct is not None else
                "<tr><td>Management fee</td><td class=n>not configured — net shown before fee</td></tr>")
    ledger_rows = "".join(
        f"<tr><td>{_e(k.removeprefix('ledger_').capitalize())}</td><td class=n>{_m(-v)}</td></tr>"
        for k, v in c.items() if k.startswith("ledger_"))
    missing = sum(p.channel_cost_missing for p in om.properties)
    prop_rows = "".join(
        f"<tr><td>{_e(p.display_name)}</td><td class=n>{p.nights_sold}</td>"
        f"<td class=n>{_m(p.gross_accommodation + p.cleaning_fees)}</td>"
        f"<td class=n>{p.turns_observed}+{p.turns_estimated}</td>"
        f"<td class=n>{'—' if not p.qa_checked else f'{p.qa_passed}/{p.qa_checked}'}</td></tr>"
        for p in om.properties)
    decisions = "".join(
        f"<li>{_e(d['property_id'])} {_e(d['stay_date'])}: {_m(d['listed_price_at_run'])} → "
        f"{_m(d['recommended_price'])}"
        f"{' · min ' + str(d['recommended_min_stay']) + ' (' + str(d['min_stay_source']) + ')' if d['recommended_min_stay'] else ''}"
        f"{' · held' if d['status'] == 'blocked' else ''}</li>"
        for d in om.decisions) or "<li>No move of $100 or more was recommended for this month's nights.</li>"
    incidents = "".join(f"<li>{_e(i['type'])} {_e(i['window'])} · {_e(i['status'])}</li>"
                        for i in om.incidents) or "<li>None.</li>"
    readiness = "".join(f"<li>{_e(r['at'][:10])} {_e(r['property_id'])}: {_e(r['from_state'])} → "
                        f"{_e(r['to_state'])} ({_e(r['actor'])})</li>" for r in om.readiness) or "<li>No changes.</li>"
    comp = "".join(f"<li>{_e(r['property_id'])}: {_e(r['label'])} — {_e(r['status'])}"
                   f"{' due ' + _e(r['deadline']) if r['deadline'] else ''}</li>"
                   for r in om.compliance) or "<li>No missing or expiring items on file.</li>"
    ev = om.asset_events
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mont Luxe owner receipt {_e(om.owner_id)} {om.month_start:%Y-%m}</title>
<style>
  body {{ font-family: "Iowan Old Style", Palatino, Georgia, serif; color: #1c1915; margin: 2rem auto; max-width: 40rem; line-height: 1.45; }}
  header, section {{ border-top: 1px solid #1c1915; padding-top: 0.8rem; margin-top: 1.2rem; }}
  h1 {{ font-size: 1.4rem; letter-spacing: 0.04em; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.05rem; margin: 0.2rem 0; }}
  .meta {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td, th {{ padding: 0.15rem 0; text-align: left; }}
  .n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .total td {{ border-top: 1px solid #1c1915; font-weight: bold; }}
  .note {{ font-size: 0.85rem; }}
  @media print {{ body {{ margin: 0.5in; }} }}
</style>
</head>
<body>
<header>
  <h1>Mont Luxe — owner receipt</h1>
  <p class="meta">{_e(om.owner_name)} · {om.month_start:%B %Y}</p>
</header>
<section>
  <h2>Net performance</h2>
  <table>
    <tr><td>Booking revenue incl. cleaning fees</td><td class=n>{_m(om.gross)}</td></tr>
    <tr><td>Channel &amp; platform cost (derived)</td><td class=n>{_m(-c['channel'])}</td></tr>
    <tr><td>Turnover &amp; spa service (invoiced)</td><td class=n>{_m(-c['service_observed'])}</td></tr>
    <tr><td>Turnover &amp; spa service (estimated, no invoice yet)</td><td class=n>{_m(-c['service_estimated'])}</td></tr>
    {ledger_rows}
    {fee_line}
    <tr class=total><td>Net to owner</td><td class=n>{_m(om.net)}</td></tr>
  </table>
  <p class=note>Revenue and channel cost are pro-rated by nights in the month; owner stays are excluded.
  Channel cost = fare + cleaning fee − host payout{f'; {missing} stay(s) lacked payout data and are not included' if missing else ''}.
  Estimated service uses the property profile until task costs are imported.</p>
  <table>
    <tr><th>Home</th><th class=n>Nights</th><th class=n>Revenue</th><th class=n>Turns (invoiced+est.)</th><th class=n>QA pass</th></tr>
    {prop_rows}
  </table>
</section>
<section>
  <h2>Revenue decisions</h2>
  <p>{om.applied_changes} rate change(s) applied in Guesty for this month's nights.</p>
  <ul>{decisions}</ul>
</section>
<section>
  <h2>Property care</h2>
  <p>{ev['opened']} issue(s) logged · {ev['resolved']} resolved · {ev['still_open']} still open.</p>
  <ul>{readiness}</ul>
</section>
<section>
  <h2>Exceptions</h2>
  <p>Incidents:</p><ul>{incidents}</ul>
  <p>Permits and documents needing attention (tracking only, not a legal determination):</p><ul>{comp}</ul>
</section>
</body>
</html>
"""


def write_owner_receipt(db_path: Path | str, owner_id: str, month: str, *,
                        output: Path | None = None, allow_placeholder_names: bool = False) -> Path:
    from src.memory.paths import assert_private_root, ensure_layout

    with connect(db_path) as conn:
        om = load_owner_month(conn, owner_id, month, allow_placeholder_names=allow_placeholder_names)
    doc = render(om)
    if output is None:
        output = ensure_layout() / "receipts" / "owner" / f"{owner_id}_{month}.html"
    else:
        output = assert_private_root(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(doc, encoding="utf-8")
    return output
