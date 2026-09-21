"""Price composer — maximizes E[RevPAN] subject to guardrails, then explains itself.

v1 chose a price by multiplying rules together and clamping to the ceiling. That
optimizes a rate. This version searches a grid over [floor, ceiling] and selects the
price maximizing `P x P(book|P)`, which is what "RevPAN is the core metric" has to
mean operationally. Multipliers now shape the SEARCH BOUNDS and the reference price
rather than being the answer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

import numpy as np

from src import bookprob
from src.ceiling import CeilingResult, compute_ceiling
from src.comps import CompEvidence, comp_evidence
from src.config import load_policy
from src.elasticity import elasticity_context, maybe_soften
from src.explain import Reason, ReasonCode, select_top_reasons
from src.explain.present import (
    owner_evidence_count,
    owner_price_range,
    serialize_owner_reason,
)
from src.features import NightFeatures, build_features
from src.guardrails import DataHealth, apply_guardrails, assess_data_health, record_health
from src.leakage import apply_leakage_price, scan_leakage
from src.min_stay import decide_min_stay
from src.utils import round_price_conservative


@dataclass
class Recommendation:
    property_id: str
    stay_date: date
    recommended_price: float
    ceiling_price: float
    floor_price: float
    listed_price_at_run: float | None
    expected_book_prob: float | None
    expected_revpan: float | None
    ceiling_confidence: float
    autonomy_level: str
    guardrail_action: str | None
    reasons: list[dict[str, Any]]
    rule_version: str
    model_version: str
    inputs_hash: str
    run_id: str
    status: str = "suggested"
    recommended_min_stay: int | None = None
    min_stay_source: str | None = None
    per_person_nightly: float | None = None
    max_occupancy: int | None = None
    # Display-only. Derived from ceiling confidence + search bounds; not a CI.
    range_low: float | None = None
    range_high: float | None = None
    evidence_count: int = 0


def _property_occupancy(conn: sqlite3.Connection, property_id: str) -> int | None:
    row = conn.execute(
        "SELECT max_occupancy FROM properties WHERE property_id = ?",
        (property_id,),
    ).fetchone()
    if row is None or row["max_occupancy"] is None:
        return None
    occ = int(row["max_occupancy"])
    return occ if occ > 0 else None


def _per_person_nightly(price: float, occupancy: int | None, policy: dict[str, Any]) -> float | None:
    """Display-only framing. Never feeds RevPAN."""
    cfg = (policy.get("display") or {}).get("per_person") or {}
    if not cfg.get("enabled", True) or occupancy is None or occupancy <= 0:
        return None
    round_to = max(1, int(cfg.get("round_to", 1)))
    return float(round(price / occupancy / round_to) * round_to)


def _search_bounds(feat: NightFeatures, ceiling: CeilingResult, policy: dict[str, Any]) -> tuple[float, float]:
    g = policy.get("global", {})
    floor = max(feat.min_floor_rate, float(g.get("min_price", 0)), ceiling.floor_price)
    ceil = min(feat.max_ceiling_rate, float(g.get("max_price", 1e9)), ceiling.ceiling_price)
    return floor, max(ceil, floor)


def _optimize_revpan(
    bp: bookprob.BookingProbability,
    floor: float,
    ceil: float,
    steps: int,
) -> tuple[float, float, float]:
    """Return (best_price, prob_at_best, expected_revpan)."""
    if ceil <= floor:
        return floor, bp.prob_at(floor), bp.expected_revpan(floor)
    grid = np.linspace(floor, ceil, max(2, steps))
    values = [bp.expected_revpan(float(p)) for p in grid]
    i = int(np.argmax(values))
    best = float(grid[i])
    return best, bp.prob_at(best), float(values[i])


def _inputs_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def recommend_night(
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any] | None = None,
    health: DataHealth | None = None,
    run_id: str = "adhoc",
    *,
    as_of: date | None = None,
    include_booked: bool = False,
) -> Recommendation | None:
    if feat.status != "available":
        if not include_booked or feat.status != "booked":
            return None
        listed = feat.listed_price if feat.listed_price is not None else feat.booked_price
        feat = replace(feat, status="available", listed_price=listed)

    policy = policy or load_policy()
    g = policy.get("global", {})
    round_to = int(g.get("round_to", 5))
    max_reasons = int(policy.get("explain", {}).get("max_reasons", 3))
    steps = int(policy.get("compose", {}).get("candidate_steps", 40))
    decision_date = as_of or date.today()

    from src.signals.features.access import access_risk as get_access_risk
    from src.signals.promotion import signal_status_at_least
    from src.signals.store import SignalStore

    store = SignalStore(conn)
    risk = 0.0
    access_cfg = policy.get("access", {})
    if access_cfg.get("enabled", True) and signal_status_at_least(
        store, "cdot.access_risk", "shadow"
    ):
        risk = get_access_risk(store, feat.market_id, decision_date)

    ceiling = compute_ceiling(conn, feat, policy, as_of=decision_date)
    floor, ceil = _search_bounds(feat, ceiling, policy)
    bp = bookprob.estimate(conn, feat, policy, as_of=decision_date)

    # 1. RevPAN optimum over the admissible band.
    optimum, prob, exp_revpan = _optimize_revpan(bp, floor, ceil, steps)

    # 2. Leakage scanners may override the optimum (orphan gaps in particular are a
    #    fill problem, not a yield problem).
    findings = scan_leakage(feat, ceiling, optimum, policy, access_risk=risk)
    leaked_price, primary_leak = apply_leakage_price(optimum, findings)

    # 2b. Min-stay decision: season × lead-time policy table, then gap override.
    gap_action = None
    if primary_leak and primary_leak.kind == "orphan_gap":
        gap_action = primary_leak.min_stay_action
    elif findings:
        for f in findings:
            if f.kind == "orphan_gap" and f.min_stay_action is not None:
                gap_action = f.min_stay_action
                break
    min_stay = decide_min_stay(feat, policy, gap_min_stay_action=gap_action)

    # 3. Elasticity softening on weak first-party conversion.
    ctx = elasticity_context(conn, feat, policy)
    softened = maybe_soften(feat.listed_price, leaked_price, ctx, policy)

    # 4. Deference to the incumbent price when our own evidence is weak. The operator
    #    set the current price deliberately; a low-confidence model must nudge it, not
    #    overrule it. See config compose.deference for the measured motivation.
    deferred = softened
    deference_shift = 0.0
    dcfg = policy.get("compose", {}).get("deference", {})
    if (dcfg.get("enabled", True) and feat.listed_price
            and ceiling.confidence < float(dcfg.get("below_confidence", 0.80))):
        w = max(float(dcfg.get("min_model_weight", 0.25)), ceiling.confidence)
        deferred = w * softened + (1.0 - w) * float(feat.listed_price)
        deference_shift = deferred - softened

    pre_guard = min(max(deferred, floor), ceil)

    # 5. Hard invariants. Never overridable.
    verdict = apply_guardrails(
        proposed=pre_guard,
        listed=feat.listed_price,
        anchor=ceiling.anchor_price,
        demand_strength=feat.demand_strength,
        policy=policy,
    )
    recommended = round_price_conservative(verdict.price, feat.listed_price, round_to)

    # 6. Autonomy: derived from data health, further demoted by thin ceilings.
    level = health.granted_level if health else "suggest"
    min_conf = float(policy.get("autonomy", {}).get("require_ceiling_confidence", 0.80))
    if ceiling.confidence < min_conf and level == "handle":
        level = "suggest"
    # Berthoud hard closure — human should decide hold vs cut.
    if (
        access_cfg.get("enabled", True)
        and risk >= 1.0
        and feat.lead_time_days is not None
        and feat.lead_time_days <= int(access_cfg.get("escalate_when_closed_lead_days", 3))
    ):
        level = "suggest"
    # Resort closure / wind-hold risk — hold rates until ops clarify.
    resort_cfg = policy.get("resort_ops", {})
    if resort_cfg.get("enabled", True) and feat.lead_time_days is not None:
        from src.signals.features.resort_ops import compute_resort_ops

        ops = compute_resort_ops(store, feat.market_id, feat.stay_date, decision_date)
        escalate_lead = int(resort_cfg.get("escalate_when_closed_lead_days", 3))
        closure_thresh = float(resort_cfg.get("closure_risk_threshold", 0.80))
        resort_closed = store.latest_observation(
            as_of=decision_date,
            signal_key="resort.resort_open",
            market_id=feat.market_id,
            effective_date=decision_date,
        )
        is_closed = (
            resort_closed is not None
            and resort_closed["value"] is not None
            and float(resort_closed["value"]) < 0.5
        )
        if feat.lead_time_days <= escalate_lead and (
            ops.closure_risk >= closure_thresh
            or (resort_cfg.get("demote_when_resort_closed", True) and is_closed)
        ):
            level = "suggest"
    if verdict.blocked:
        level = "escalate"

    # ---- attribution -------------------------------------------------------
    listed = feat.listed_price
    reasons: list[Reason] = []
    ev: CompEvidence | None = comp_evidence(conn, feat, policy)
    # Typed explicitly against the ReasonCode taxonomy so a future new LeakKind
    # with no mapping here fails mypy instead of silently reaching src/explain
    # with an unlisted code.
    leak_codes: dict[str, ReasonCode] = {
        "peak_underprice": "ceiling_gap",
        "orphan_gap": "gap_night",
        "shoulder_over_discount": "shoulder_floor",
        "access_cliff": "access_cliff",
    }

    if listed is not None:
        reasons.append(Reason(
            "revpan_optimum",
            f"E[RevPAN] peaks at ${optimum:.0f} (P(book)={bp.prob_at(optimum):.0%}, "
            f"beta={bp.beta:.2f}, bucket {bp.bucket} n={bp.sample_size})",
            contribution=optimum - listed,
            facts={"optimum": optimum, "book_prob": bp.prob_at(optimum)},
        ))
    reasons.append(Reason(
        "base_compose",
        f"Ceiling ${ceiling.ceiling_price:.0f} via {ceiling.method} "
        f"(n={ceiling.sample_size}, confidence {ceiling.confidence:.0%})",
        contribution=0.0,
        facts={
            "ceiling": ceiling.ceiling_price,
            "season": feat.season,
            "thin": ceiling.is_thin,
        },
    ))
    if ceiling.is_thin:
        reasons.append(Reason(
            "thin_history",
            f"Thin {feat.season} history — ceiling blended {1 - ceiling.confidence:.0%} "
            f"toward the ${ceiling.anchor_price:.0f} seasonal anchor",
            contribution=(ceiling.ceiling_price - ceiling.anchor_price) * (1 - ceiling.confidence),
            facts={
                "kind": "thin_pool",
                "season": feat.season,
                "anchor": ceiling.anchor_price,
            },
        ))
    if ceiling.comp_price is not None:
        reasons.append(Reason(
            "comp_move",
            f"Comp set p75 ${ceiling.comp_price:.0f} (weight {ceiling.comp_weight:.0%})",
            contribution=(ceiling.comp_price - ceiling.anchor_price) * ceiling.comp_weight,
            facts={
                "comp_price": ceiling.comp_price,
                "comp_observed": ev.observed if ev is not None else 0,
            },
        ))
    if ceiling.substitution_reduction_pct > 0 and ceiling.substitution_index is not None:
        drop = ceiling.ceiling_price * ceiling.substitution_reduction_pct
        reasons.append(Reason(
            "substitution_bleed",
            f"Substitutes cheaper per SQI (index {ceiling.substitution_index:.2f}) — "
            f"ceiling capped −{ceiling.substitution_reduction_pct:.0%}",
            contribution=-drop,
            facts={"reduction_pct": ceiling.substitution_reduction_pct},
        ))
    if feat.demand_event and feat.demand_strength >= 0.5:
        reasons.append(Reason(
            "event_boost",
            f"{feat.demand_event} (demand {feat.demand_strength:.2f})",
            contribution=0.0,
            facts={"event": feat.demand_event},
        ))
    if bp.pacing_ratio is not None:
        reasons.append(Reason(
            "pacing",
            f"Pacing {bp.pacing_ratio:.2f}x the portfolio norm at this lead time",
            contribution=0.0,
            facts={"pacing_ratio": bp.pacing_ratio},
        ))
    shoulder_cfg = (policy.get("leakage") or {}).get("shoulder_over_discount") or {}
    shoulder_floor = ceiling.floor_price * float(shoulder_cfg.get("floor_ratio", 0.95))
    standing_min = min_stay.policy_min_stay if min_stay.policy_min_stay is not None else feat.min_stay
    for f in findings:
        code = leak_codes.get(f.kind)
        if code:
            reasons.append(Reason(
                code,
                f.detail,
                contribution=f.suggested_adjustment - optimum,
                facts={
                    "listed": listed,
                    "ceiling": ceiling.ceiling_price,
                    "event": feat.demand_event or "high demand",
                    "gap_size": feat.gap_size,
                    "standing_min_stay": standing_min,
                    "shoulder_floor": shoulder_floor,
                    "lead_days": feat.lead_time_days,
                },
            ))
    if min_stay.recommended_min_stay is not None:
        reasons.append(Reason(
            "min_stay",
            min_stay.detail,
            contribution=0.0,
            always_show=min_stay.gap_override,
            facts={
                "nights": min_stay.recommended_min_stay,
                "source": min_stay.source,
                "gap_override": min_stay.gap_override,
            },
        ))
    if ctx.soften_upward:
        reasons.append(Reason(
            "inquiry_soft",
            ctx.note,
            contribution=softened - leaked_price,
            facts={"conversion_rate": ctx.conversion_rate},
        ))
    if abs(deference_shift) >= 1.0:
        reasons.append(Reason(
            "thin_history",
            f"Low ceiling confidence ({ceiling.confidence:.0%}) — held "
            f"{1 - max(float(dcfg.get('min_model_weight', 0.25)), ceiling.confidence):.0%} "
            f"toward your listed ${feat.listed_price:.0f}",
            contribution=deference_shift,
            facts={"kind": "deference", "listed": feat.listed_price},
        ))
    if verdict.action:
        reasons.append(Reason(
            "guardrail",
            f"{verdict.action}: {verdict.detail}",
            contribution=verdict.price - pre_guard,
            always_show=True,
            facts={"action": verdict.action},
        ))

    top = select_top_reasons(reasons, max_n=max_reasons)
    occupancy = _property_occupancy(conn, feat.property_id)
    per_person = _per_person_nightly(recommended, occupancy, policy)
    range_low, range_high = owner_price_range(
        recommended=recommended,
        floor=floor,
        ceiling=ceil,
        confidence=ceiling.confidence,
        round_to=round_to,
    )
    evidence_count = owner_evidence_count(
        own_history_nights=ceiling.sample_size,
        comp_usable=bool(ev is not None and ev.usable),
        comp_observed=ev.observed if ev is not None else 0,
        demand_event=bool(feat.demand_event and feat.demand_strength >= 0.5),
        pacing_present=bp.pacing_ratio is not None,
        substitution_applied=ceiling.substitution_reduction_pct > 0,
        inquiry_softened=ctx.soften_upward,
        access_capped=any(f.kind == "access_cliff" for f in findings),
    )
    payload = {
        "property_id": feat.property_id, "stay_date": feat.stay_date.isoformat(),
        "listed": listed, "optimum": optimum, "ceiling": ceiling.ceiling_price,
        "floor": floor, "beta": bp.beta, "p_ref": bp.p_ref,
        "min_stay": min_stay.recommended_min_stay,
        "min_stay_source": min_stay.source,
        "rule_version": policy.get("rule_version"), "model_version": policy.get("model_version"),
    }
    return Recommendation(
        property_id=feat.property_id,
        stay_date=feat.stay_date,
        recommended_price=recommended,
        ceiling_price=ceiling.ceiling_price,
        floor_price=floor,
        listed_price_at_run=listed,
        expected_book_prob=bp.prob_at(recommended),
        expected_revpan=bp.expected_revpan(recommended),
        ceiling_confidence=ceiling.confidence,
        autonomy_level=level,
        guardrail_action=verdict.action,
        reasons=[serialize_owner_reason(r) for r in top],
        rule_version=str(policy.get("rule_version", "unknown")),
        model_version=str(policy.get("model_version", "rules_v2")),
        inputs_hash=_inputs_hash(payload),
        run_id=run_id,
        status="blocked" if verdict.blocked else "suggested",
        recommended_min_stay=min_stay.recommended_min_stay,
        min_stay_source=min_stay.source,
        per_person_nightly=per_person,
        max_occupancy=occupancy,
        range_low=range_low,
        range_high=range_high,
        evidence_count=evidence_count,
    )


def persist_recommendation(conn: sqlite3.Connection, rec: Recommendation) -> int:
    cur = conn.execute(
        """
        INSERT INTO price_recommendations (
            run_id, property_id, stay_date, recommended_price, ceiling_price, floor_price,
            listed_price_at_run, expected_book_prob, expected_revpan, ceiling_confidence,
            autonomy_level, guardrail_action, reasons, rule_version, model_version,
            inputs_hash, status, recommended_min_stay, min_stay_source, per_person_nightly,
            range_low, range_high, evidence_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, property_id, stay_date) DO UPDATE SET
            recommended_price=excluded.recommended_price,
            expected_book_prob=excluded.expected_book_prob,
            expected_revpan=excluded.expected_revpan,
            guardrail_action=excluded.guardrail_action,
            reasons=excluded.reasons, status=excluded.status,
            recommended_min_stay=excluded.recommended_min_stay,
            min_stay_source=excluded.min_stay_source,
            per_person_nightly=excluded.per_person_nightly,
            range_low=excluded.range_low,
            range_high=excluded.range_high,
            evidence_count=excluded.evidence_count
        """,
        (rec.run_id, rec.property_id, rec.stay_date.isoformat(), rec.recommended_price,
         rec.ceiling_price, rec.floor_price, rec.listed_price_at_run, rec.expected_book_prob,
         rec.expected_revpan, rec.ceiling_confidence, rec.autonomy_level, rec.guardrail_action,
         json.dumps(rec.reasons), rec.rule_version, rec.model_version, rec.inputs_hash, rec.status,
         rec.recommended_min_stay, rec.min_stay_source, rec.per_person_nightly,
         rec.range_low, rec.range_high, rec.evidence_count),
    )
    # cur.lastrowid is unreliable here: on the ON CONFLICT DO UPDATE branch
    # sqlite does not update last_insert_rowid(), so it would silently return
    # the id of a PRIOR, unrelated insert rather than this row's id (or None
    # before any row has ever been inserted on this connection). Nothing
    # currently consumes this return value, but a future caller (e.g. audit
    # linking) must get the real id, not a stale one.
    row = conn.execute(
        "SELECT id FROM price_recommendations WHERE run_id = ? AND property_id = ? AND stay_date = ?",
        (rec.run_id, rec.property_id, rec.stay_date.isoformat()),
    ).fetchone()
    if row is None:
        raise RuntimeError(
            f"persist_recommendation: no row found after upsert for "
            f"{rec.run_id}/{rec.property_id}/{rec.stay_date}"
        )
    return int(row["id"])


def generate_recommendations(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_ids: list[str] | None = None,
    policy: dict[str, Any] | None = None,
    persist: bool = True,
    run_id: str | None = None,
    allow_past: bool = False,
    *,
    as_of: date | None = None,
) -> tuple[list[Recommendation], DataHealth]:
    policy = policy or load_policy()
    run_id = run_id or uuid.uuid4().hex[:12]
    health = assess_data_health(conn, policy, property_ids=property_ids)
    if persist:
        record_health(conn, run_id, health)

    features = build_features(conn, start, end, property_ids=property_ids, policy=policy, as_of=as_of)
    if not allow_past:
        # Pricing a night that has already happened is always a bug in a live run.
        # Backtests must opt in explicitly.
        today = date.today()
        features = [f for f in features if f.stay_date >= today]
    recs: list[Recommendation] = []
    for feat in features:
        rec = recommend_night(
            conn, feat, policy=policy, health=health, run_id=run_id, as_of=as_of
        )
        if rec is None:
            continue
        if persist:
            persist_recommendation(conn, rec)
        recs.append(rec)
    if persist:
        conn.commit()
    return recs, health
