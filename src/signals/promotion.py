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
        age = (as_of - date.fromisoformat(str(row["last"])[:10])).days
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
