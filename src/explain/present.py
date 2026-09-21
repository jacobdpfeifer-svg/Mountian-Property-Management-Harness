"""Owner-facing rendering of ranked Reason objects.

Ranking and dollar contributions live in `select_top_reasons` and src/compose.
This module only translates already-ranked reasons into plain language, and
derives a display range / evidence count from fields the engine already computed.

It is a presentation layer. It does not choose a price.
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable

from src.explain import Reason
from src.utils import round_price

# Codes src/compose currently constructs. Tests fail if compose emits a new code
# that is not in OWNER_TEMPLATES — there is no silent fallback to internals.
COMPOSE_REASON_CODES: frozenset[str] = frozenset({
    "revpan_optimum",
    "base_compose",
    "thin_history",
    "comp_move",
    "substitution_bleed",
    "event_boost",
    "pacing",
    "ceiling_gap",
    "gap_night",
    "shoulder_floor",
    "access_cliff",
    "min_stay",
    "inquiry_soft",
    "guardrail",
})

# Tokens that must never appear in the default owner surface.
JARGON_TOKEN_RE = re.compile(r"(?i)\b(?:beta|sqi|bucket)\b|n=")


class MissingOwnerTemplateError(KeyError):
    """Raised when a reason code has no owner-facing template."""


def _money(value: Any) -> str:
    return f"${float(value):.0f}"


def _pct(value: Any) -> str:
    return f"{float(value) * 100:.0f}%"


def _season_label(value: Any) -> str:
    raw = str(value or "").replace("_", " ").strip()
    return raw if raw else "this"


def _event_label(value: Any) -> str:
    raw = str(value or "").strip()
    return raw if raw else "a high-demand event"


def _nights(value: Any) -> str:
    n = int(value) if value is not None else 0
    return f"{n} night" if n == 1 else f"{n} nights"


def _tpl_revpan_optimum(f: dict[str, Any]) -> str:
    optimum = f.get("optimum")
    book_prob = f.get("book_prob")
    if optimum is None:
        return "This rate is set where expected nightly revenue is highest."
    if book_prob is None:
        return (
            f"Expected nightly revenue is highest around {_money(optimum)}."
        )
    chance = int(round(float(book_prob) * 100))
    return (
        f"Expected nightly revenue is highest around {_money(optimum)}, "
        f"with about a {chance}% chance of booking at that rate."
    )


def _tpl_base_compose(f: dict[str, Any]) -> str:
    ceiling = f.get("ceiling")
    season = _season_label(f.get("season"))
    if ceiling is None:
        return f"The top of the range is based on what this home has achieved on similar {season} nights."
    if f.get("thin"):
        return (
            f"The top of the range is {_money(ceiling)} for this {season} night, "
            f"leaning on the usual seasonal level because comparable booked nights are scarce."
        )
    return (
        f"The top of the range for this {season} night is {_money(ceiling)}, "
        f"based on what this home has actually booked before."
    )


def _tpl_thin_history(f: dict[str, Any]) -> str:
    if f.get("kind") == "deference":
        listed = f.get("listed")
        if listed is not None:
            return (
                "The model is not sure enough of the ceiling yet, so this stays "
                f"closer to your current listed rate of {_money(listed)}."
            )
        return (
            "The model is not sure enough of the ceiling yet, so this stays "
            "closer to your current listed rate."
        )
    season = _season_label(f.get("season"))
    anchor = f.get("anchor")
    if anchor is not None:
        return (
            f"This {season} season has few comparable booked nights, so the rate "
            f"stays closer to the usual {_money(anchor)} level."
        )
    return (
        f"This {season} season has few comparable booked nights, so the rate "
        "stays closer to the usual seasonal level."
    )


def _tpl_comp_move(f: dict[str, Any]) -> str:
    price = f.get("comp_price")
    observed = int(f.get("comp_observed") or 0)
    if price is None:
        return "Comparable large-group homes in your market are pricing differently than this listing."
    if observed > 0:
        noun = "comp confirms" if observed == 1 else "comps confirm"
        return (
            f"Comparable large-group homes in your market are listing around "
            f"{_money(price)} ({observed} {noun})."
        )
    return (
        f"Comparable large-group homes in your market are listing around {_money(price)}."
    )


def _tpl_substitution_bleed(f: dict[str, Any]) -> str:
    drop = f.get("reduction_pct")
    if drop:
        return (
            "Similar homes in nearby mountain towns are cheaper right now, so the "
            f"top of the range is pulled down {_pct(drop)}."
        )
    return (
        "Similar homes in nearby mountain towns are cheaper right now, so the "
        "top of the range is pulled down."
    )


def _tpl_event_boost(f: dict[str, Any]) -> str:
    return f"{_event_label(f.get('event'))} is drawing strong demand for this night."


def _tpl_pacing(f: dict[str, Any]) -> str:
    ratio = f.get("pacing_ratio")
    if ratio is None:
        return "This home's booking pace differs from the rest of the portfolio at this lead time."
    if float(ratio) >= 1.0:
        return "This home is booking ahead of the rest of the portfolio at this lead time."
    return "This home is booking behind the rest of the portfolio at this lead time."


def _tpl_ceiling_gap(f: dict[str, Any]) -> str:
    event = _event_label(f.get("event"))
    listed = f.get("listed")
    ceiling = f.get("ceiling")
    if listed is not None and ceiling is not None:
        return (
            f"The listed {_money(listed)} is well below what {event} can support "
            f"(top of the range {_money(ceiling)})."
        )
    return f"The listed rate is well below what {event} can support."


def _tpl_gap_night(f: dict[str, Any]) -> str:
    gap = f.get("gap_size")
    standing = f.get("standing_min_stay")
    hole = _nights(gap) if gap is not None else "a short hole"
    if standing is not None and gap is not None and int(standing) > int(gap):
        return (
            f"There is a {hole} hole between bookings, but the standing minimum stay "
            f"is {int(standing)} nights — relax the minimum so the hole can sell."
        )
    return (
        f"There is a {hole} hole between bookings — a gap-fill rate helps it sell."
    )


def _tpl_shoulder_floor(f: dict[str, Any]) -> str:
    listed = f.get("listed")
    floor = f.get("shoulder_floor")
    if listed is not None and floor is not None:
        return (
            f"This is a quieter night, but {_money(listed)} is below a productive "
            f"floor of {_money(floor)}."
        )
    return "This is a quieter night, but the listed rate is below a productive floor."


def _tpl_access_cliff(f: dict[str, Any]) -> str:
    lead = f.get("lead_days")
    if lead is not None:
        return (
            f"Highway access looks risky in the next {int(lead)} days, so the rate "
            "is not raised much above the current listing."
        )
    return (
        "Highway access looks risky in the coming days, so the rate is not raised "
        "much above the current listing."
    )


def _tpl_min_stay(f: dict[str, Any]) -> str:
    nights = f.get("nights")
    if f.get("gap_override"):
        if nights is not None:
            return (
                f"Relax the minimum stay to {_nights(nights)} so the gap between "
                "bookings can sell."
            )
        return "Relax the minimum stay so the gap between bookings can sell."
    source = f.get("source")
    if nights is not None and source == "policy":
        return (
            f"Minimum stay is {_nights(nights)} for this season and booking window."
        )
    if nights is not None:
        return f"Minimum stay is {_nights(nights)}."
    return "A minimum-stay rule applies to this night."


def _tpl_inquiry_soft(f: dict[str, Any]) -> str:
    conv = f.get("conversion_rate")
    if conv is not None:
        return (
            f"Recent inquiries are converting at {_pct(conv)}, so an upward move "
            "was held back."
        )
    return "Recent inquiries are converting poorly at the quoted rate, so an upward move was held back."


def _tpl_guardrail(f: dict[str, Any]) -> str:
    action = str(f.get("action") or "")
    if action == "clamped_increase":
        return "The suggested increase was capped so it stays within the allowed move from your current listing."
    if action == "clamped_decrease":
        return "The suggested decrease was capped so it stays within the allowed move from your current listing."
    if action == "sanity_floor":
        return "The suggested rate was too far below this home's usual seasonal level, so it was raised to a safe floor."
    if action == "peak_blackout":
        return "This is a peak night that requires a person to approve the rate before it is published."
    return "A pricing safety rule adjusted this rate."


def _tpl_lead_time(f: dict[str, Any]) -> str:
    days = f.get("lead_days")
    if days is not None:
        return f"Lead time of {int(days)} days is shaping how far the rate can move."
    return "How far out this night sits is shaping the rate."


def _tpl_dow(f: dict[str, Any]) -> str:
    return "The day of week for this stay is shaping the rate."


def _tpl_season(f: dict[str, Any]) -> str:
    return f"This is a {_season_label(f.get('season'))} night, which sets the seasonal level."


OWNER_TEMPLATES: dict[str, Callable[[dict[str, Any]], str]] = {
    "revpan_optimum": _tpl_revpan_optimum,
    "base_compose": _tpl_base_compose,
    "thin_history": _tpl_thin_history,
    "comp_move": _tpl_comp_move,
    "substitution_bleed": _tpl_substitution_bleed,
    "event_boost": _tpl_event_boost,
    "pacing": _tpl_pacing,
    "ceiling_gap": _tpl_ceiling_gap,
    "gap_night": _tpl_gap_night,
    "shoulder_floor": _tpl_shoulder_floor,
    "access_cliff": _tpl_access_cliff,
    "min_stay": _tpl_min_stay,
    "inquiry_soft": _tpl_inquiry_soft,
    "guardrail": _tpl_guardrail,
    "lead_time": _tpl_lead_time,
    "dow": _tpl_dow,
    "season": _tpl_season,
}


def render_owner_reason(reason: Reason | dict[str, Any]) -> str:
    """Plain-English sentence for one ranked reason. Fails if the code is unmapped."""
    if isinstance(reason, Reason):
        code = str(reason.code)
        facts = reason.facts
    else:
        code = str(reason.get("code") or "")
        facts = dict(reason.get("facts") or {})
    tpl = OWNER_TEMPLATES.get(code)
    if tpl is None:
        raise MissingOwnerTemplateError(
            f"No owner-facing template for reason code {code!r}. "
            "Add a template in src/explain/present.py; do not fall back to internals."
        )
    return tpl(facts)


def serialize_owner_reason(reason: Reason) -> dict[str, Any]:
    """Default stored surface is owner-facing; internals stay under technical_message."""
    return {
        "code": reason.code,
        "message": render_owner_reason(reason),
        "technical_message": reason.message,
        "contribution": round(reason.contribution, 2),
    }


def owner_price_range(
    *,
    recommended: float,
    floor: float,
    ceiling: float,
    confidence: float,
    round_to: int = 5,
) -> tuple[float, float]:
    """Display range around the recommended point.

    This is not a statistical confidence interval. The engine searches a grid on
    [floor, ceiling] and returns one argmax (then guardrails/rounding). There is
    no posterior width in the current outputs.

    Half-width is therefore derived from the ceiling confidence the engine already
    computes: high confidence narrows the band; thin history widens it. The band
    is always clipped to the same [floor, ceiling] that bounded the RevPAN search,
    and always contains the recommended point.
    """
    lo_bound = min(floor, ceiling)
    hi_bound = max(floor, ceiling)
    conf = min(1.0, max(0.0, float(confidence)))
    # 3% of price at full confidence; 18% at zero confidence.
    half_pct = 0.03 + 0.15 * (1.0 - conf)
    step = max(1, int(round_to))
    half = max(float(step), abs(recommended) * half_pct)
    raw_lo = recommended - half
    raw_hi = recommended + half
    lo = max(lo_bound, min(recommended, raw_lo))
    hi = min(hi_bound, max(recommended, raw_hi))
    lo = float(math.floor(lo / step) * step)
    hi = float(math.ceil(hi / step) * step)
    lo = max(lo_bound, min(recommended, lo))
    hi = min(hi_bound, max(recommended, hi))
    if lo > recommended:
        lo = recommended
    if hi < recommended:
        hi = recommended
    return round_price(lo, step), round_price(hi, step)


def owner_evidence_count(
    *,
    own_history_nights: int,
    comp_usable: bool,
    comp_observed: int,
    demand_event: bool,
    pacing_present: bool,
    substitution_applied: bool,
    inquiry_softened: bool,
    access_capped: bool,
) -> int:
    """Count independent evidence *streams* that actually entered this night.

    Comps count as one stream (the curated set), not one per listing. Per-comp
    counts belong on the comp_move sentence via `comp_observed`. Own history
    counts as one stream whether the ceiling used booked nights or the seasonal
    anchor — both are first-party evidence, never invented.
    """
    n = 1  # first-party ceiling (history or seasonal anchor)
    if own_history_nights <= 0:
        pass  # still 1: the anchor was used
    if comp_usable and comp_observed > 0:
        n += 1
    if demand_event:
        n += 1
    if pacing_present:
        n += 1
    if substitution_applied:
        n += 1
    if inquiry_softened:
        n += 1
    if access_capped:
        n += 1
    return n


def format_evidence_label(count: int) -> str:
    if count <= 0:
        return ""
    if count == 1:
        return "1 SOURCE"
    return f"{count} SOURCES AGREE"


def format_owner_recommendation(rec: Any, *, technical: bool = False) -> str:
    """CLI / owner-report block: range, evidence count, one sentence per top reason."""
    listed = getattr(rec, "listed_price_at_run", None)
    listed_s = f"${listed:.0f}" if listed is not None else "-"
    low = getattr(rec, "range_low", None)
    high = getattr(rec, "range_high", None)
    point = float(rec.recommended_price)
    if low is None or high is None:
        range_s = f"${point:.0f}"
    else:
        range_s = f"${float(low):.0f}–${float(high):.0f}"
    delta = ""
    if listed:
        pct = (point - float(listed)) / float(listed)
        delta = f" ({pct:+.1%} vs listed)"
    flag = f"  [{rec.status.upper()}]" if getattr(rec, "status", "") == "blocked" else ""
    los = ""
    if getattr(rec, "recommended_min_stay", None) is not None:
        src = getattr(rec, "min_stay_source", "") or ""
        los = f"  min stay {rec.recommended_min_stay} ({src})"
    pp = ""
    if getattr(rec, "per_person_nightly", None) is not None:
        occ = getattr(rec, "max_occupancy", None)
        pp = f"  ${rec.per_person_nightly:.0f}/person"
        if occ:
            pp += f"/{occ}"
    ev = format_evidence_label(int(getattr(rec, "evidence_count", 0) or 0))
    ev_s = f"  {ev}" if ev else ""
    lines = [
        f"  {rec.property_id:14} {rec.stay_date}  {listed_s:>7} -> "
        f"{range_s}  recommend ${point:.0f}{delta}{ev_s}  "
        f"{rec.autonomy_level}{los}{pp}{flag}"
    ]
    for r in rec.reasons:
        if technical:
            text = r.get("technical_message") or r.get("message") or ""
        else:
            text = r.get("message") or ""
        lines.append(f"      {text}")
    return "\n".join(lines)


def owner_text_has_jargon(text: str) -> bool:
    return bool(JARGON_TOKEN_RE.search(text))
