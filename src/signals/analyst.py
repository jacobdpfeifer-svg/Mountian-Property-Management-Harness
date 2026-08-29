"""Weekly analyst briefs (WP-14) — prose for humans, structurally unable to move a price.

This module never imports compose, ceiling, or PMS push paths.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.signals.store import SignalStore


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
