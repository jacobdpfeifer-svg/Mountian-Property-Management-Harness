"""Local HTML run receipt. Sentences come from stored recommendation JSON."""

from __future__ import annotations

import html
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import load_portfolio_config
from src.db import connect
from src.memory.paths import ensure_layout

TWIN_IDS = ("summit_haus", "overlook_ridge")
MOVE_CARD_DOLLARS = 100.0


@dataclass
class NightRow:
    recommendation_id: int
    property_id: str
    stay_date: date
    recommended_price: float
    ceiling_price: float
    floor_price: float
    listed_price: float | None
    autonomy_level: str
    guardrail_action: str | None
    reasons: list[dict[str, Any]]
    status: str
    weak_ceiling: bool
    inputs_hash: str
    rule_version: str
    model_version: str
    range_low: float | None
    range_high: float | None
    memory_set_hash: str | None
    memory_feature_version: str | None
    memory_claim_refs: list[str]
    memory_counterfactual_price: float | None
    created_at: str


@dataclass
class Card:
    property_id: str
    rows: list[NightRow]
    primary: bool
    twin_split: bool = False
    label: str = ""


@dataclass
class ReceiptFacts:
    run_id: str
    nights: list[NightRow]
    granted_level: str | None
    failures: list[str]
    health_as_of: str | None
    pushed: int
    pushed_ids: set[int] = field(default_factory=set)
    pending_claims: list[dict[str, Any]] = field(default_factory=list)


def _display_names() -> dict[str, str]:
    cfg = load_portfolio_config()
    names = {}
    for pid, meta in (cfg.get("properties") or {}).items():
        names[pid] = str(meta.get("display_name") or pid)
    return names


def _parse_reasons(raw: str | None) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _parse_refs(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(item) for item in data]
    return []


def _load(conn: sqlite3.Connection, run_id: str) -> ReceiptFacts:
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(price_recommendations)").fetchall()
    }
    memory_cols = ""
    if "memory_set_hash" in cols:
        memory_cols = """
            , memory_set_hash, memory_feature_version, memory_claim_refs,
              memory_counterfactual_price
        """
    rows = conn.execute(
        f"""
        SELECT id, property_id, stay_date, recommended_price, ceiling_price, floor_price,
               listed_price_at_run, autonomy_level, guardrail_action, reasons, status,
               weak_ceiling, inputs_hash, rule_version, model_version, range_low, range_high,
               created_at
               {memory_cols}
        FROM price_recommendations
        WHERE run_id = ?
        ORDER BY property_id, stay_date
        """,
        (run_id,),
    ).fetchall()
    nights: list[NightRow] = []
    for row in rows:
        keys = row.keys()
        nights.append(NightRow(
            recommendation_id=int(row["id"]),
            property_id=row["property_id"],
            stay_date=date.fromisoformat(row["stay_date"]),
            recommended_price=float(row["recommended_price"]),
            ceiling_price=float(row["ceiling_price"]),
            floor_price=float(row["floor_price"]),
            listed_price=None if row["listed_price_at_run"] is None else float(row["listed_price_at_run"]),
            autonomy_level=row["autonomy_level"],
            guardrail_action=row["guardrail_action"],
            reasons=_parse_reasons(row["reasons"]),
            status=row["status"],
            weak_ceiling=bool(row["weak_ceiling"]),
            inputs_hash=row["inputs_hash"],
            rule_version=row["rule_version"],
            model_version=row["model_version"],
            range_low=None if row["range_low"] is None else float(row["range_low"]),
            range_high=None if row["range_high"] is None else float(row["range_high"]),
            memory_set_hash=row["memory_set_hash"] if "memory_set_hash" in keys else None,
            memory_feature_version=row["memory_feature_version"] if "memory_feature_version" in keys else None,
            memory_claim_refs=_parse_refs(row["memory_claim_refs"]) if "memory_claim_refs" in keys else [],
            memory_counterfactual_price=(
                None if "memory_counterfactual_price" not in keys or row["memory_counterfactual_price"] is None
                else float(row["memory_counterfactual_price"])
            ),
            created_at=row["created_at"] or "",
        ))
    health = conn.execute(
        "SELECT as_of, granted_level, failures FROM data_health_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    failures: list[str] = []
    granted = None
    health_as_of = None
    if health is not None:
        granted = health["granted_level"]
        health_as_of = health["as_of"]
        try:
            parsed = json.loads(health["failures"] or "[]")
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            failures = [str(item) for item in parsed]
    ids = [night.recommendation_id for night in nights]
    pushed_ids: set[int] = set()
    if ids:
        marks = ",".join("?" for _ in ids)
        pushed_ids = {
            int(row["recommendation_id"])
            for row in conn.execute(
                f"""
                SELECT recommendation_id FROM rate_changes
                WHERE recommendation_id IN ({marks}) AND result = 'applied'
                """,
                ids,
            )
            if row["recommendation_id"] is not None
        }
    return ReceiptFacts(
        run_id=run_id,
        nights=nights,
        granted_level=granted,
        failures=failures,
        health_as_of=health_as_of,
        pushed=len(pushed_ids),
        pushed_ids=pushed_ids,
    )


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"


def _move(night: NightRow) -> float:
    if night.listed_price is None:
        return 0.0
    return night.recommended_price - night.listed_price


def _reason_codes(night: NightRow) -> tuple[str, ...]:
    return tuple(str(reason.get("code") or "") for reason in night.reasons)


def _stored_sentences(night: NightRow) -> list[str]:
    """Only sentences already stored on the recommendation. Never invent one."""
    sentences = []
    for reason in night.reasons:
        message = reason.get("message")
        if isinstance(message, str) and message.strip():
            sentences.append(message.strip())
    return sentences


def _twin_split_dates(nights: list[NightRow]) -> set[date]:
    by_date: dict[date, dict[str, NightRow]] = {}
    for night in nights:
        by_date.setdefault(night.stay_date, {})[night.property_id] = night
    splits: set[date] = set()
    for stay, props in by_date.items():
        left = props.get(TWIN_IDS[0])
        right = props.get(TWIN_IDS[1])
        if left is None or right is None:
            continue
        if abs(_move(left) - _move(right)) >= 1:
            splits.add(stay)
    return splits


def _signature(night: NightRow) -> tuple[Any, ...]:
    return (
        _reason_codes(night),
        night.guardrail_action,
        night.autonomy_level,
        tuple(night.memory_claim_refs),
        night.weak_ceiling,
        night.status,
    )


def _is_primary(night: NightRow, splits: set[date], pushed_ids: set[int]) -> bool:
    if night.property_id in TWIN_IDS and night.stay_date in splits:
        return True
    if night.status == "blocked" or night.autonomy_level == "escalate":
        return True
    if night.autonomy_level == "handle" and night.recommendation_id not in pushed_ids:
        return True
    if abs(_move(night)) >= MOVE_CARD_DOLLARS:
        return True
    return False


def _cluster(facts: ReceiptFacts) -> list[Card]:
    splits = _twin_split_dates(facts.nights)
    pushed_ids = facts.pushed_ids
    cards: list[Card] = []
    by_property: dict[str, list[NightRow]] = {}
    for night in facts.nights:
        by_property.setdefault(night.property_id, []).append(night)
    for property_id, nights in by_property.items():
        nights.sort(key=lambda item: item.stay_date)
        bucket: list[NightRow] = []
        bucket_primary = False

        def flush() -> None:
            nonlocal bucket, bucket_primary
            if not bucket:
                return
            watch = any(item.weak_ceiling for item in bucket) or any(abs(_move(item)) >= 1 for item in bucket)
            if bucket_primary or watch:
                cards.append(Card(
                    property_id=property_id,
                    rows=list(bucket),
                    primary=bucket_primary,
                    twin_split=any(item.stay_date in splits and property_id in TWIN_IDS for item in bucket),
                ))
            bucket = []
            bucket_primary = False

        for night in nights:
            primary = _is_primary(night, splits, pushed_ids)
            own_card = primary or night.weak_ceiling
            if own_card:
                flush()
                cards.append(Card(
                    property_id=property_id,
                    rows=[night],
                    primary=primary,
                    twin_split=property_id in TWIN_IDS and night.stay_date in splits,
                ))
                continue
            if bucket and (
                night.stay_date != bucket[-1].stay_date + timedelta(days=1)
                or _signature(night) != _signature(bucket[-1])
            ):
                flush()
            bucket.append(night)
            bucket_primary = False
        flush()
    cards.sort(key=lambda card: (
        not card.primary,
        -max(abs(_move(night)) for night in card.rows),
        card.property_id,
        card.rows[0].stay_date,
    ))
    return cards


def _position(facts: ReceiptFacts) -> str:
    parts: list[str] = []
    if facts.granted_level != "handle":
        parts.append("Suggestions only")
    if any("comp" in failure.lower() for failure in facts.failures):
        parts.append("comp coverage is thin")
    if facts.pushed == 0:
        parts.append("nothing was pushed")
    if not parts:
        return "Rates were eligible to write. Guesty remains the rate record."
    return "; ".join(parts) + "."


def _held(facts: ReceiptFacts) -> int:
    held = 0
    for night in facts.nights:
        if night.listed_price is None:
            continue
        if abs(_move(night)) < 1 and night.autonomy_level in {"suggest", "watch"}:
            held += 1
    return held


def _fmt_span(rows: list[NightRow]) -> str:
    start = rows[0].stay_date.strftime("%b %-d")
    if len(rows) == 1:
        return start
    return f"{start}–{rows[-1].stay_date.strftime('%-d')}"


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _card_html(card: Card, names: dict[str, str], nights: list[NightRow]) -> str:
    night = card.rows[0]
    name = names.get(card.property_id, card.property_id)
    sentences = []
    for row in card.rows:
        for sentence in _stored_sentences(row):
            if sentence not in sentences:
                sentences.append(sentence)
    sentence_html = "".join(f"<p>{_e(sentence)}</p>" for sentence in sentences)
    path = (
        f"floor {_money(night.floor_price)} → listed {_money(night.listed_price)} → "
        f"recommended {_money(night.recommended_price)} → ceiling {_money(night.ceiling_price)}"
    )
    twin = ""
    if card.twin_split:
        others = [
            other for other in nights
            if other.stay_date == night.stay_date and other.property_id != card.property_id
            and other.property_id in TWIN_IDS
        ]
        if others:
            other = others[0]
            twin = (
                f"<p class=\"twin\">Twin check: { _e(names.get(card.property_id, card.property_id)) } "
                f"{_money(_move(night))} / { _e(names.get(other.property_id, other.property_id)) } "
                f"{_money(_move(other))}. Different listed rate or evidence, not a hidden shared policy.</p>"
            )
    audit_bits = [
        f"reason codes: {', '.join(_reason_codes(night)) or 'none'}",
        f"inputs_hash {night.inputs_hash}",
        f"rule {night.rule_version}",
        f"model {night.model_version}",
    ]
    if night.guardrail_action:
        audit_bits.append(f"guardrail {night.guardrail_action}")
    if night.weak_ceiling:
        audit_bits.append("weak ceiling")
    if night.memory_set_hash:
        audit_bits.append(f"memory {night.memory_set_hash}")
    if night.memory_claim_refs:
        audit_bits.append("claims " + ", ".join(night.memory_claim_refs))
    if night.memory_counterfactual_price is not None:
        audit_bits.append(
            f"without this claim {_money(night.memory_counterfactual_price)}"
        )
    contributions = []
    for reason in night.reasons:
        if "contribution" in reason:
            contributions.append(
                f"{reason.get('code')}: {reason.get('contribution')}"
            )
    if contributions:
        audit_bits.append("contributions " + "; ".join(contributions))
    heading = "Look at these first" if card.primary else "Also watch"
    return f"""
    <article class="card">
      <p class="kicker">{_e(heading)}</p>
      <h2>{_e(name)} · {_e(_fmt_span(card.rows))}</h2>
      <p class="path">{_e(path)}</p>
      {sentence_html}
      {twin}
      <p class="guesty">Open this date in Guesty. Guesty is the rate record.</p>
      <details>
        <summary>Exact receipt</summary>
        <p>{_e(" · ".join(audit_bits))}</p>
      </details>
    </article>
    """


def render_receipt(facts: ReceiptFacts, *, pending: list[dict[str, Any]] | None = None) -> str:
    names = _display_names()
    cards = _cluster(facts)
    primary = [card for card in cards if card.primary]
    watch = [card for card in cards if not card.primary]
    created = facts.nights[0].created_at if facts.nights else (facts.health_as_of or "")
    try:
        stamp = datetime.fromisoformat(created.replace(" ", "T"))
        when = stamp.strftime("%a %b %-d, %-I:%M %p UTC")
    except ValueError:
        when = created or "undated run"
    scope = " · ".join(
        names.get(pid, pid)
        for pid in ("summit_haus", "overlook_ridge", "cloud_9")
    )
    if not cards:
        body = "<p class=\"quiet\">No decision needs you.</p>"
    else:
        body = "".join(_card_html(card, names, facts.nights) for card in [*primary, *watch])
    failure_lines = "".join(f"<li>{_e(item)}</li>" for item in facts.failures)
    if not failure_lines:
        failure_lines = "<li>No health failures stored for this run.</li>"
    pending = pending if pending is not None else facts.pending_claims
    if pending:
        items = []
        for claim in pending:
            label = names.get(str(claim.get("property_id") or ""), str(claim.get("property_id") or "unspecified"))
            items.append(
                "<li>"
                + _e(
                    f"{claim.get('claim_id')} · {label} · {claim.get('stay_from') or '—'}–"
                    f"{claim.get('stay_to') or '—'} · {claim.get('kind')} · {claim.get('status')}"
                )
                + "</li>"
            )
        inbox = "<ul>" + "".join(items) + "</ul>"
    else:
        inbox = "<p>No claim is waiting. A dropped file stays quarantined until you confirm a typed claim.</p>"
    position = _position(facts)
    suggested = len(facts.nights)
    held = _held(facts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mont Luxe run receipt {_e(facts.run_id)}</title>
<style>
  body {{ font-family: "Iowan Old Style", Palatino, Georgia, serif; color: #1c1915; margin: 2rem auto; max-width: 40rem; line-height: 1.45; }}
  header, article, section {{ border-top: 1px solid #1c1915; padding-top: 0.8rem; margin-top: 1.2rem; }}
  h1 {{ font-size: 1.4rem; letter-spacing: 0.04em; margin-bottom: 0.2rem; }}
  h2 {{ font-size: 1.05rem; margin: 0.2rem 0; }}
  .meta, .kicker, .guesty, summary {{ font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 0.78rem; letter-spacing: 0.04em; text-transform: uppercase; }}
  .path {{ font-variant-numeric: tabular-nums; }}
  .quiet {{ font-size: 1.3rem; }}
  @media print {{ body {{ margin: 0.5in; }} }}
</style>
</head>
<body>
<header>
  <h1>Mont Luxe — run receipt</h1>
  <p class="meta">{_e(when)} · {_e(facts.run_id)}</p>
  <p>Scope: {_e(scope)}. Guesty is the rate record.</p>
</header>
<section>
  <h2>Today's position</h2>
  <p>{_e(position)}</p>
  <p>Since last receipt: {suggested} suggested · {facts.pushed} pushed · {held} held · {len(pending)} memory claim pending.</p>
</section>
{body}
<section>
  <h2>Trust timeline</h2>
  <ul>
    <li>{_e(facts.health_as_of or "health time not stored")} · granted { _e(facts.granted_level or "unknown") }</li>
    {failure_lines}
    <li>{facts.pushed} channel writes</li>
  </ul>
</section>
<section>
  <h2>Evidence inbox</h2>
  <p>Finder › Mont Luxe Evidence Inbox. A file cannot set a price. Confirm a typed claim before it can raise a floor.</p>
  {inbox}
</section>
</body>
</html>
"""


def load_pending_claims() -> list[dict[str, Any]]:
    from src.memory.claims import pending_summaries
    from src.memory.db import connect_memory
    from src.memory.paths import default_memory_root

    root = default_memory_root()
    if not (root / "operator_memory.db").exists():
        return []
    conn = connect_memory(root)
    try:
        return pending_summaries(conn)
    finally:
        conn.close()


def write_receipt(
    db_path: Path | str,
    run_id: str,
    *,
    output: Path | None = None,
) -> Path:
    with connect(db_path) as conn:
        facts = _load(conn, run_id)
    if not facts.nights and facts.granted_level is None:
        raise LookupError(run_id)
    try:
        facts.pending_claims = load_pending_claims()
    except Exception:
        facts.pending_claims = []
    document = render_receipt(facts)
    if output is None:
        day = facts.nights[0].stay_date.isoformat() if facts.nights else date.today().isoformat()
        # Receipts are grouped by the run's stored timestamp date when present.
        created = facts.nights[0].created_at if facts.nights else ""
        folder_day = created[:10] if len(created) >= 10 else day
        output = ensure_layout() / "receipts" / folder_day / f"{run_id}.html"
    else:
        from src.memory.paths import assert_private_root
        output = assert_private_root(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output
