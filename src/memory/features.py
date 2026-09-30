"""The only pricing-facing memory API. It never reads file bytes."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.memory.claims import PRICE_KINDS
from src.memory.paths import assert_private_root, default_memory_root

FEATURE_VERSION = "memory_features_v1"
EMPTY_HASH = "memory_features_v1:empty"
# Confirmation stamps are stored in UTC. The decision date is a Mountain Time
# day, so an evening confirmation must count that same day.
_OPERATOR_TZ = ZoneInfo("America/Denver")


@dataclass(frozen=True)
class MemoryFeatures:
    schema_version: str = FEATURE_VERSION
    memory_set_hash: str = EMPTY_HASH
    active_claim_refs: list[str] = field(default_factory=list)
    effective_floor_raise: float = 0.0
    counterfactual_floor_raise: float = 0.0
    floor_above_ceiling: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "memory_set_hash": self.memory_set_hash,
            "active_claim_refs": list(self.active_claim_refs),
            "effective_floor_raise": self.effective_floor_raise,
            "counterfactual_floor_raise": self.counterfactual_floor_raise,
        }


def empty_features() -> MemoryFeatures:
    return MemoryFeatures()


def _day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _accepted_day(value: str | None) -> date | None:
    """Calendar day in Mountain Time for a UTC confirmation stamp."""
    if not value:
        return None
    text = str(value).strip()
    if "T" not in text:
        return _day(text)
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return _day(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(_OPERATOR_TZ).date()


def _open_readonly(root: Path) -> sqlite3.Connection | None:
    db_path = root / "operator_memory.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def build_memory_features(
    property_id: str,
    stay_date: date,
    as_of: date,
    *,
    listed_price: float | None = None,
    policy_floor: float | None = None,
    ceiling: float | None = None,
    root: Path | None = None,
) -> MemoryFeatures:
    """Active, as-of claims for one property-night. Missing store means empty."""
    store = assert_private_root(root if root is not None else default_memory_root())
    if not store.exists():
        return empty_features()
    conn = _open_readonly(store)
    if conn is None:
        return empty_features()
    try:
        rows = conn.execute(
            """
            SELECT c.* FROM memory_claims c
            JOIN (
                SELECT claim_id, MAX(revision) AS revision
                FROM memory_claims GROUP BY claim_id
            ) latest
              ON c.claim_id = latest.claim_id AND c.revision = latest.revision
            WHERE c.property_id = ?
              AND c.status = 'active'
              AND c.effect_class = 'price_bearing'
              AND c.kind IN ('minimum_rate', 'no_decrease')
            ORDER BY c.claim_id, c.revision
            """,
            (property_id,),
        ).fetchall()
    finally:
        conn.close()

    selected: list[tuple[str, str, float]] = []
    floor = float(policy_floor or 0.0)
    for row in rows:
        if row["kind"] not in PRICE_KINDS:
            continue
        accepted = _accepted_day(row["accepted_at"])
        if accepted is None or accepted > as_of:
            continue
        review = _day(row["review_after"])
        if review is not None and as_of > review:
            continue
        start = _day(row["stay_from"])
        end = _day(row["stay_to"])
        if start is None or end is None or not (start <= stay_date <= end):
            continue
        try:
            value = json.loads(row["value_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if row["kind"] == "no_decrease":
            if listed_price is None:
                continue
            target = float(listed_price)
        else:
            if "minimum" not in value:
                continue
            try:
                target = float(value["minimum"])
            except (TypeError, ValueError):
                continue
        if not math.isfinite(target) or target <= 0:
            continue
        ref = f"claim:{row['claim_id']}@{int(row['revision'])}"
        selected.append((ref, row["kind"], target))

    if not selected:
        return empty_features()

    selected.sort(key=lambda item: item[0])
    effective = max(floor, *(target for _ref, _kind, target in selected))
    raise_amt = max(0.0, effective - floor)
    conflict = ceiling is not None and effective > float(ceiling)
    payload = {
        "schema_version": FEATURE_VERSION,
        "claims": [
            {"ref": ref, "kind": kind, "target": target}
            for ref, kind, target in selected
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    return MemoryFeatures(
        memory_set_hash=f"sha256:{digest}",
        active_claim_refs=[ref for ref, _kind, _target in selected],
        effective_floor_raise=raise_amt,
        counterfactual_floor_raise=0.0,
        floor_above_ceiling=conflict,
    )
