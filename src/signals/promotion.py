"""Signal scoring & promotion ladder (WP-13). SQI is NOT on this ladder."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from src.config import load_yaml
from src.eval.backtest import score_signal_against_outcomes
from src.signals.store import SignalStore

ROOT = Path(__file__).resolve().parents[2]
SIGNALS_POLICY = ROOT / "config" / "policies" / "signals.yaml"


def load_signals_policy(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or SIGNALS_POLICY)


def register_ladder_signals(store: SignalStore) -> None:
    """Synthetic ladder entries for compose-gated signals without collectors."""
    from src.signals.store import SignalDefinition

    extras = [
        SignalDefinition(
            "substitution.market_bleed",
            "cross_market",
            "ratio",
            "daily",
            "substitution_index",
            status="experimental",
            description="Cross-valley price-per-SQI bleed cap",
        ),
    ]
    for d in extras:
        store.upsert_definition(d)


def rescore_all(
    store: SignalStore,
    conn,
    decision_dates: list[date],
    *,
    horizon_days: int = 14,
) -> list[dict[str, Any]]:
    results = []
    for dfn in store.list_definitions():
        key = dfn["signal_key"]
        if dfn["status"] == "deprecated":
            continue
        results.append(
            score_signal_against_outcomes(
                store, conn, key, decision_dates=decision_dates, horizon_days=horizon_days
            )
        )
    return results


def apply_promotions(store: SignalStore, policy: dict[str, Any] | None = None) -> list[str]:
    """Move signals across experimental→shadow→active→deprecated from latest scores."""
    cfg = (policy or load_signals_policy()).get("ladder", {})
    actions: list[str] = []
    for dfn in store.list_definitions():
        key = dfn["signal_key"]
        status = dfn["status"]
        score = store.conn.execute(
            """
            SELECT * FROM signal_scores WHERE signal_key = ?
            ORDER BY scored_at DESC LIMIT 1
            """,
            (key,),
        ).fetchone()
        if score is None:
            continue
        decision = score["decision"]
        n = int(score["sample_size"] or 0)
        ic = score["information_coefficient"]
        hr = score["hit_rate"]

        shadow_cfg = cfg.get("shadow_to_active", {})
        if status == "experimental" and n >= int(
            cfg.get("experimental_to_shadow", {}).get("min_observations", 30)
        ):
            store.set_status(key, "shadow")
            actions.append(f"{key}: experimental→shadow")
        elif (
            status == "shadow"
            and decision == "promote"
            and n >= int(shadow_cfg.get("min_sample_size", 40))
            and (ic or -1) >= float(shadow_cfg.get("min_information_coefficient", 0.05))
            and (hr or 0) >= float(shadow_cfg.get("min_hit_rate", 0.52))
        ):
            store.set_status(key, "active")
            actions.append(f"{key}: shadow→active")
        elif status == "active" and decision == "demote":
            store.set_status(key, "deprecated")
            actions.append(f"{key}: active→deprecated")
        elif status in ("shadow", "active") and decision == "demote":
            store.set_status(key, "deprecated")
            actions.append(f"{key}: {status}→deprecated")
    return actions


def demote_on_source_break(store: SignalStore, signal_key: str) -> None:
    """Broken source → deprecated; features must fall back without price discontinuity."""
    store.set_status(signal_key, "deprecated")


STATUS_RANK = {"deprecated": -1, "experimental": 0, "shadow": 1, "active": 2}


def signal_status_at_least(
    store: SignalStore,
    signal_key: str,
    min_status: str = "shadow",
) -> bool:
    """True when a ladder signal has reached min_status (SQI is not on the ladder)."""
    dfn = store.get_definition(signal_key)
    if dfn is None:
        return False
    return STATUS_RANK.get(dfn["status"], 0) >= STATUS_RANK.get(min_status, 1)


def signal_freshness_failures(
    store: SignalStore, as_of: date, policy: dict[str, Any] | None = None
) -> list[str]:
    """Fold into data-health gate: stale active signals demote autonomy."""
    fresh = (policy or load_signals_policy()).get("freshness", {})
    failures = []
    for dfn in store.list_definitions(status="active"):
        key = dfn["signal_key"]
        row = store.conn.execute(
            """
            SELECT MAX(observed_at) AS last FROM signal_observations
            WHERE signal_key = ? AND quality = 'ok'
            """,
            (key,),
        ).fetchone()
        if not row or not row["last"]:
            failures.append(f"active signal {key} has no ok observations")
            continue
        last_ts = str(row["last"])
        last_date = date.fromisoformat(last_ts[:10])
        if key.startswith("cdot"):
            from datetime import datetime

            max_hours = int(fresh.get("cdot_max_age_hours", 6))
            try:
                last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                as_of_dt = datetime(as_of.year, as_of.month, as_of.day)
                age_hours = (as_of_dt - last_dt.replace(tzinfo=None)).total_seconds() / 3600.0
            except ValueError:
                age_hours = (as_of - last_date).days * 24.0
            if age_hours > max_hours:
                failures.append(
                    f"active signal {key} stale ({age_hours:.1f}h > {max_hours}h)"
                )
            continue
        age = (as_of - last_date).days
        # map collector prefix to policy
        max_age = 7
        if key.startswith("snotel"):
            max_age = int(fresh.get("snotel_max_age_days", 3))
        elif key.startswith("weather"):
            max_age = int(fresh.get("weather_max_age_days", 2))
        elif key.startswith("resort"):
            max_age = int(fresh.get("resort_max_age_days", 2))
        if age > max_age:
            failures.append(f"active signal {key} stale ({age}d > {max_age}d)")
    return failures
