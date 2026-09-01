"""Weekly analyst briefs (WP-14) — prose for humans, structurally unable to move a price.

This module never imports compose, ceiling, or PMS push paths.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from src.signals.store import SignalStore


def resort_brief(store: SignalStore, as_of: date, *, market_id: str = "grand_home") -> str:
    """Winter Park ops brief — lift/terrain/closures for owners and guests."""
    from src.signals.features.resort_ops import compute_resort_ops, lift_diff_summary

    lines = [
        f"# Winter Park Resort ops brief — as of {as_of.isoformat()}",
        "",
        "This brief cannot change prices. Operational intelligence only.",
        "",
    ]

    snap = store.latest_resort_snapshot(as_of=as_of, market_id=market_id)
    if snap:
        lines.append("## Mountain status")
        lines.append(
            f"- Lifts open: {snap['lift_open']}/{snap['lift_total']}  "
            f"Trails open: {snap['trail_open']}/{snap['trail_total']}"
        )
        lines.append(f"- Snapshot date: {snap['as_of']}")
    else:
        lines.append("## Mountain status")
        lines.append("- No resort snapshot yet. Run `wp-price signals cycle`.")

    lines.append("")
    lines.append("## Lift changes since prior snapshot")
    for line in lift_diff_summary(store, market_id, as_of):
        lines.append(line)

    lines.append("")
    lines.append("## Forecast priors (rules-based, wide bands)")
    ops = compute_resort_ops(store, market_id, as_of, as_of)
    lines.append(f"- Closure risk: {ops.closure_risk:.0%} (confidence {ops.confidence:.0%})")
    lines.append(f"- Lift hold risk: {ops.lift_hold_risk:.0%}")
    lines.append(f"- Terrain open forecast: {ops.terrain_open_forecast:.0%}")
    lines.append(f"- Surface: {ops.surface_label} (score {ops.surface_forecast_score:.2f})")
    lines.append(f"- Staffing readiness prior: {ops.staffing_readiness:.0%}")

    lines.append("")
    lines.append("## Berthoud / access")
    berthoud = store.latest_observation(
        as_of=as_of,
        signal_key="cdot.berthoud_closed",
        market_id=market_id,
        effective_date=as_of,
    )
    chain = store.latest_observation(
        as_of=as_of,
        signal_key="cdot.chain_law",
        market_id=market_id,
        effective_date=as_of,
    )
    if berthoud and berthoud["value"] is not None:
        closed = float(berthoud["value"]) >= 0.5
        chain_on = chain and chain["value"] is not None and float(chain["value"]) >= 0.5
        if closed:
            lines.append("- US-40 Berthoud Pass: **CLOSED**")
        elif chain_on:
            lines.append("- US-40 Berthoud Pass: open with chain law")
        else:
            lines.append("- US-40 Berthoud Pass: open")
    else:
        lines.append("- No CDOT access observation.")

    lines.append("")
    lines.append("## Grooming coverage")
    groomed = store.latest_observation(
        as_of=as_of,
        signal_key="resort.trails_groomed_pct",
        market_id=market_id,
        effective_date=as_of,
    )
    if groomed and groomed["value"] is not None:
        lines.append(f"- Trails groomed (among open): {float(groomed['value']):.0f}%")
        week_ago = as_of - timedelta(days=7)
        prior = store.read_observations(
            as_of=as_of,
            signal_key="resort.trails_groomed_pct",
            market_id=market_id,
            effective_from=week_ago,
            effective_to=as_of - timedelta(days=1),
            qualities=["ok"],
        )
        if prior:
            avg = sum(float(r["value"]) for r in prior) / len(prior)
            lines.append(f"- 7-day prior average: {avg:.0f}%")
    else:
        lines.append("- No grooming coverage observation.")

    lines.append("")
    lines.append("## Guest / owner talking points")
    talking: list[str] = []
    from src.signals.features.resort_ops import _in_ski_season
    from src.config import load_resort_config

    in_season = _in_ski_season(as_of, load_resort_config())
    if in_season and ops.closure_risk >= 0.6:
        talking.append("- High wind-hold or closure risk — avoid promising specific lifts/terrain.")
    elif not in_season:
        talking.append("- Off-season — resort closed for skiing; do not promise ski-in access.")
    if ops.surface_label in {"fresh_powder", "packed_powder"}:
        talking.append("- Strong surface conditions — highlight recent snow or grooming.")
    elif ops.surface_label == "spring_corn":
        talking.append("- Spring conditions — set expectations for variable surfaces.")
    if not snap or (snap["lift_open"] or 0) == 0:
        if in_season:
            talking.append("- Resort fully shut — confirm lift status before ski-in messaging.")
    if not talking:
        talking.append("- Standard ops — no exceptional conditions flagged.")
    lines.extend(talking)

    return "\n".join(lines) + "\n"


def weekly_brief(store: SignalStore, as_of: date) -> str:
    """What changed, what it implies, what needs a decision — with provenance."""
    lines = [
        f"# Pfeifer Optimization weekly brief — as of {as_of.isoformat()}",
        "",
        "This brief cannot change prices. It summarises observations only.",
        "",
    ]
    runs = store.conn.execute(
        """
        SELECT collector, status, observations, rejected, as_of, errors
        FROM signal_runs
        ORDER BY started_at DESC LIMIT 20
        """
    ).fetchall()
    lines.append("## Recent collector runs")
    if not runs:
        lines.append("- No signal runs yet.")
    for r in runs:
        lines.append(
            f"- {r['collector']} @ {r['as_of']}: {r['status']} "
            f"({r['observations']} ok, {r['rejected']} rejected)"
        )

    lines.append("")
    lines.append("## Active signals")
    for d in store.list_definitions(status="active"):
        lines.append(f"- {d['signal_key']} ({d['source']})")
    if not store.list_definitions(status="active"):
        lines.append("- None active yet (expected in year one).")

    lines.append("")
    lines.append("## Flight capacity (brief-only)")
    flight = store.latest_observation(
        as_of=as_of,
        signal_key="flight.den_capacity_yoy",
        market_id="grand_home",
        effective_date=as_of,
    )
    if flight and flight["value"] is not None:
        lines.append(
            f"- DEN→mountain seat capacity YoY: {float(flight['value']):+.0%} "
            f"(analyst brief — no price effect while brief_only=true)"
        )
    else:
        lines.append("- No flight capacity observation this week.")

    lines.append("")
    lines.append("## Winter Park ops (summary)")
    snap = store.latest_resort_snapshot(as_of=as_of, market_id="grand_home")
    if snap:
        lines.append(
            f"- Lifts {snap['lift_open']}/{snap['lift_total']}, "
            f"trails {snap['trail_open']}/{snap['trail_total']} "
            f"(snapshot {snap['as_of']})"
        )
    else:
        lines.append("- No resort snapshot — run signals cycle.")
    lines.append("- Full ops detail: `wp-price signals resort-brief`")

    lines.append("")
    lines.append("## Decisions needed")
    lines.append(
        "- Review SQI kill switch if ceilings look wrong "
        "(config/policies/conditions.yaml → sqi.enabled)."
    )
    lines.append(
        "- f(SQI) is a declared prior with wide bands — not a fitted finding."
    )
    return "\n".join(lines) + "\n"


def narrate_anomaly(
    store: SignalStore,
    *,
    feature_key: str,
    market_id: str,
    effective_date: date,
    as_of: date,
    threshold: float = 0.15,
) -> str | None:
    row = store.read_feature(
        as_of=as_of,
        feature_key=feature_key,
        market_id=market_id,
        effective_date=effective_date,
    )
    if row is None or row["value"] is None:
        return None
    # Compare to prior feature if any
    prior = store.conn.execute(
        """
        SELECT value FROM signal_features
        WHERE feature_key = ? AND market_id = ? AND effective_date < ? AND as_of <= ?
        ORDER BY effective_date DESC LIMIT 1
        """,
        (feature_key, market_id, effective_date.isoformat(), as_of.isoformat()),
    ).fetchone()
    if prior is None or prior["value"] is None:
        return (
            f"{feature_key} for {market_id} on {effective_date} = {row['value']:.3f} "
            f"(no prior; inputs_hash={row['inputs_hash']})."
        )
    delta = float(row["value"]) - float(prior["value"])
    if abs(delta) < threshold:
        return None
    return (
        f"{feature_key} for {market_id} moved {delta:+.3f} to {row['value']:.3f} "
        f"on {effective_date} (inputs_hash={row['inputs_hash']}). "
        f"Provenance is in signal_observations feeding this feature."
    )
