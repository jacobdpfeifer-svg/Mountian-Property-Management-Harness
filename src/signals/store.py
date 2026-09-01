"""Signal Store — system of record for observations and features.

Contract (WP-01):
  * Every read that reconstructs decision-time state REQUIRES an `as_of` argument
    and filters `observed_at <= as_of`. No lookahead, ever.
  * Writers are idempotent on their natural unique keys.
  * Agents never write prices here — only observations and (via builders) features.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from src.config import load_yaml

ROOT = Path(__file__).resolve().parents[2]
MARKETS_PATH = ROOT / "config" / "policies" / "markets.yaml"

QUALITY_OK = "ok"
QUALITY_UNAVAILABLE = "unavailable"
QUALITY_FAILED = "failed"
QUALITY_BLOCKED = "blocked"
QUALITY_STALE = "stale"
QUALITIES = frozenset(
    {QUALITY_OK, QUALITY_UNAVAILABLE, QUALITY_FAILED, QUALITY_BLOCKED, QUALITY_STALE}
)

STATUSES = frozenset({"experimental", "shadow", "active", "deprecated"})


def _iso(d: date | datetime | str) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class Observation:
    signal_key: str
    market_id: str
    observed_at: str
    effective_date: str
    value: float | None
    horizon_days: int = 0
    confidence: float = 1.0
    quality: str = QUALITY_OK
    provenance_url: str | None = None
    run_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.quality not in QUALITIES:
            raise ValueError(f"invalid quality: {self.quality}")
        self.observed_at = _iso(self.observed_at)
        self.effective_date = _iso(self.effective_date)


@dataclass
class SignalDefinition:
    signal_key: str
    category: str
    unit: str
    cadence: str
    source: str
    status: str = "experimental"
    schema_version: str = "1"
    description: str = ""
    value_min: float | None = None
    value_max: float | None = None
    collector: str | None = None


class SignalStore:
    """Typed persistence for Pfeifer Optimization."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------------ markets

    def seed_markets(self, path: Path | None = None) -> int:
        data = load_yaml(path or MARKETS_PATH)
        markets = data.get("markets", [])
        n = 0
        for m in markets:
            bbox = m.get("bbox") or {}
            cen = m.get("centroid") or {}
            self.conn.execute(
                """
                INSERT INTO markets (
                    market_id, name, ring, county, region_legacy,
                    bbox_ne_lat, bbox_ne_lng, bbox_sw_lat, bbox_sw_lng,
                    centroid_lat, centroid_lng, snotel_stations, active
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)
                ON CONFLICT(market_id) DO UPDATE SET
                    name=excluded.name,
                    ring=excluded.ring,
                    county=excluded.county,
                    region_legacy=excluded.region_legacy,
                    bbox_ne_lat=excluded.bbox_ne_lat,
                    bbox_ne_lng=excluded.bbox_ne_lng,
                    bbox_sw_lat=excluded.bbox_sw_lat,
                    bbox_sw_lng=excluded.bbox_sw_lng,
                    centroid_lat=excluded.centroid_lat,
                    centroid_lng=excluded.centroid_lng,
                    snotel_stations=excluded.snotel_stations,
                    active=1
                """,
                (
                    m["market_id"],
                    m["name"],
                    m["ring"],
                    m.get("county"),
                    m.get("region_legacy"),
                    bbox.get("ne_lat"),
                    bbox.get("ne_lng"),
                    bbox.get("sw_lat"),
                    bbox.get("sw_lng"),
                    cen.get("lat"),
                    cen.get("lng"),
                    json.dumps(m.get("snotel_stations") or []),
                ),
            )
            n += 1
        self.conn.commit()
        return n

    def list_markets(self, *, active_only: bool = True) -> list[sqlite3.Row]:
        q = "SELECT * FROM markets"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY ring, market_id"
        return list(self.conn.execute(q).fetchall())

    def get_market(self, market_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM markets WHERE market_id = ?", (market_id,)
        ).fetchone()

    def market_id_for_region(self, region: str) -> str | None:
        row = self.conn.execute(
            "SELECT market_id FROM markets WHERE region_legacy = ?", (region,)
        ).fetchone()
        return row["market_id"] if row else None

    # ------------------------------------------------------------- definitions

    def upsert_definition(self, defn: SignalDefinition) -> None:
        if defn.status not in STATUSES:
            raise ValueError(f"invalid status: {defn.status}")
        self.conn.execute(
            """
            INSERT INTO signal_definitions (
                signal_key, category, unit, cadence, source, status,
                schema_version, description, value_min, value_max, collector, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            ON CONFLICT(signal_key) DO UPDATE SET
                category=excluded.category,
                unit=excluded.unit,
                cadence=excluded.cadence,
                source=excluded.source,
                schema_version=excluded.schema_version,
                description=excluded.description,
                value_min=excluded.value_min,
                value_max=excluded.value_max,
                collector=excluded.collector,
                updated_at=datetime('now')
            """,
            (
                defn.signal_key,
                defn.category,
                defn.unit,
                defn.cadence,
                defn.source,
                defn.status,
                defn.schema_version,
                defn.description,
                defn.value_min,
                defn.value_max,
                defn.collector,
            ),
        )
        self.conn.commit()

    def get_definition(self, signal_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM signal_definitions WHERE signal_key = ?", (signal_key,)
        ).fetchone()

    def list_definitions(self, *, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return list(
                self.conn.execute(
                    "SELECT * FROM signal_definitions WHERE status = ? ORDER BY signal_key",
                    (status,),
                ).fetchall()
            )
        return list(
            self.conn.execute(
                "SELECT * FROM signal_definitions ORDER BY signal_key"
            ).fetchall()
        )

    def set_status(self, signal_key: str, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"invalid status: {status}")
        self.conn.execute(
            "UPDATE signal_definitions SET status = ?, updated_at = datetime('now') "
            "WHERE signal_key = ?",
            (status, signal_key),
        )
        self.conn.commit()

    # ---------------------------------------------------------- resort snapshots

    def write_resort_snapshot(
        self,
        *,
        as_of: date | str,
        market_id: str,
        payload: dict[str, Any],
        source_url: str | None = None,
        lift_open: int | None = None,
        lift_total: int | None = None,
        trail_open: int | None = None,
        trail_total: int | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO resort_snapshots (
                as_of, market_id, payload_json, source_url,
                lift_open, lift_total, trail_open, trail_total
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(as_of, market_id) DO UPDATE SET
                payload_json=excluded.payload_json,
                source_url=excluded.source_url,
                lift_open=excluded.lift_open,
                lift_total=excluded.lift_total,
                trail_open=excluded.trail_open,
                trail_total=excluded.trail_total
            """,
            (
                _iso(as_of),
                market_id,
                json.dumps(payload),
                source_url,
                lift_open,
                lift_total,
                trail_open,
                trail_total,
            ),
        )
        self.conn.commit()

    def latest_resort_snapshot(
        self,
        *,
        as_of: date | str,
        market_id: str,
        before_as_of: date | str | None = None,
    ) -> sqlite3.Row | None:
        """Most recent snapshot on or before as_of (or before_as_of if set)."""
        cutoff = _iso(before_as_of or as_of)
        return self.conn.execute(
            """
            SELECT * FROM resort_snapshots
            WHERE market_id = ? AND as_of <= ?
            ORDER BY as_of DESC LIMIT 1
            """,
            (market_id, cutoff),
        ).fetchone()

    def prior_resort_snapshot(
        self,
        *,
        as_of: date | str,
        market_id: str,
    ) -> sqlite3.Row | None:
        """Snapshot strictly before as_of (for diffing lift changes)."""
        return self.conn.execute(
            """
            SELECT * FROM resort_snapshots
            WHERE market_id = ? AND as_of < ?
            ORDER BY as_of DESC LIMIT 1
            """,
            (market_id, _iso(as_of)),
        ).fetchone()

    def list_resort_events(
        self,
        *,
        resort_id: str = "winter_park",
        event_type: str | None = None,
        from_date: date | str | None = None,
        to_date: date | str | None = None,
    ) -> list[sqlite3.Row]:
        clauses = ["resort_id = ?"]
        params: list[Any] = [resort_id]
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if from_date:
            clauses.append("event_date >= ?")
            params.append(_iso(from_date))
        if to_date:
            clauses.append("event_date <= ?")
            params.append(_iso(to_date))
        sql = (
            "SELECT * FROM resort_events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY event_date"
        )
        return list(self.conn.execute(sql, params).fetchall())

    def upsert_resort_event(
        self,
        *,
        resort_id: str,
        event_date: date | str,
        event_type: str,
        entity_name: str | None = None,
        notes: str | None = None,
        source_url: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO resort_events (
                resort_id, event_date, event_type, entity_name, notes, source_url
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                resort_id,
                _iso(event_date),
                event_type,
                entity_name,
                notes,
                source_url,
            ),
        )
        self.conn.commit()

    def seed_resort_events(self, events: Iterable[dict[str, Any]]) -> int:
        n = 0
        for ev in events:
            self.upsert_resort_event(
                resort_id=ev.get("resort_id", "winter_park"),
                event_date=ev["event_date"],
                event_type=ev["event_type"],
                entity_name=ev.get("entity_name"),
                notes=ev.get("notes"),
                source_url=ev.get("source_url"),
            )
            n += 1
        return n

    def upsert_season_stat(
        self,
        *,
        resort_id: str,
        stat_key: str,
        value: float,
        unit: str,
        month: int | None = None,
        season: str | None = None,
        source: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO resort_season_stats (
                resort_id, stat_key, month, season, value, unit, source
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(resort_id, stat_key, month, season) DO UPDATE SET
                value=excluded.value,
                unit=excluded.unit,
                source=excluded.source
            """,
            (resort_id, stat_key, month, season, float(value), unit, source),
        )
        self.conn.commit()

    def read_season_stats(
        self,
        *,
        resort_id: str = "winter_park",
        stat_key: str | None = None,
    ) -> list[sqlite3.Row]:
        if stat_key:
            return list(
                self.conn.execute(
                    "SELECT * FROM resort_season_stats WHERE resort_id = ? AND stat_key = ?",
                    (resort_id, stat_key),
                ).fetchall()
            )
        return list(
            self.conn.execute(
                "SELECT * FROM resort_season_stats WHERE resort_id = ? ORDER BY stat_key, month",
                (resort_id,),
            ).fetchall()
        )

    # ------------------------------------------------------------------- runs

    def start_run(
        self,
        collector: str,
        as_of: date | str,
        market_id: str | None = None,
        run_id: str | None = None,
    ) -> str:
        rid = run_id or f"sig_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO signal_runs (run_id, collector, market_id, as_of, status)
            VALUES (?,?,?,?, 'running')
            """,
            (rid, collector, market_id, _iso(as_of)),
        )
        self.conn.commit()
        return rid

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        observations: int = 0,
        rejected: int = 0,
        errors: list[str] | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE signal_runs
            SET finished_at = datetime('now'), status = ?, observations = ?,
                rejected = ?, errors = ?
            WHERE run_id = ?
            """,
            (status, observations, rejected, json.dumps(errors or []), run_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------ observations

    def write_observations(self, observations: Iterable[Observation]) -> int:
        """Idempotent upsert. Returns count of rows written (including no-ops)."""
        n = 0
        for obs in observations:
            if obs.quality not in QUALITIES:
                raise ValueError(f"invalid quality: {obs.quality}")
            self.conn.execute(
                """
                INSERT INTO signal_observations (
                    signal_key, market_id, observed_at, effective_date, horizon_days,
                    value, confidence, quality, provenance_url, run_id, meta_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(signal_key, market_id, observed_at, effective_date, horizon_days)
                DO UPDATE SET
                    value=excluded.value,
                    confidence=excluded.confidence,
                    quality=excluded.quality,
                    provenance_url=excluded.provenance_url,
                    run_id=excluded.run_id,
                    meta_json=excluded.meta_json
                """,
                (
                    obs.signal_key,
                    obs.market_id,
                    obs.observed_at,
                    obs.effective_date,
                    int(obs.horizon_days),
                    obs.value,
                    float(obs.confidence),
                    obs.quality,
                    obs.provenance_url,
                    obs.run_id,
                    json.dumps(obs.meta or {}),
                ),
            )
            n += 1
        self.conn.commit()
        return n

    def read_observations(
        self,
        *,
        as_of: date | str,
        signal_key: str | None = None,
        market_id: str | None = None,
        effective_date: date | str | None = None,
        effective_from: date | str | None = None,
        effective_to: date | str | None = None,
        qualities: Iterable[str] | None = None,
    ) -> list[sqlite3.Row]:
        """Leak-free read: ONLY rows with observed_at <= as_of are returned."""
        as_of_s = _iso(as_of)
        clauses = ["observed_at <= ?"]
        params: list[Any] = [as_of_s]
        if signal_key:
            clauses.append("signal_key = ?")
            params.append(signal_key)
        if market_id:
            clauses.append("market_id = ?")
            params.append(market_id)
        if effective_date:
            clauses.append("effective_date = ?")
            params.append(_iso(effective_date))
        if effective_from:
            clauses.append("effective_date >= ?")
            params.append(_iso(effective_from))
        if effective_to:
            clauses.append("effective_date <= ?")
            params.append(_iso(effective_to))
        if qualities:
            qs = list(qualities)
            clauses.append(f"quality IN ({','.join('?' * len(qs))})")
            params.extend(qs)
        sql = (
            "SELECT * FROM signal_observations WHERE "
            + " AND ".join(clauses)
            + " ORDER BY effective_date, observed_at"
        )
        return list(self.conn.execute(sql, params).fetchall())

    def latest_observation(
        self,
        *,
        as_of: date | str,
        signal_key: str,
        market_id: str,
        effective_date: date | str,
        horizon_days: int | None = None,
    ) -> sqlite3.Row | None:
        """Most recently observed value for a (signal, market, effective_date) as of as_of."""
        clauses = [
            "signal_key = ?",
            "market_id = ?",
            "effective_date = ?",
            "observed_at <= ?",
            "quality = 'ok'",
        ]
        params: list[Any] = [
            signal_key,
            market_id,
            _iso(effective_date),
            _iso(as_of),
        ]
        if horizon_days is not None:
            clauses.append("horizon_days = ?")
            params.append(int(horizon_days))
        sql = (
            "SELECT * FROM signal_observations WHERE "
            + " AND ".join(clauses)
            + " ORDER BY observed_at DESC, horizon_days ASC LIMIT 1"
        )
        return self.conn.execute(sql, params).fetchone()

    # --------------------------------------------------------------- features

    def write_feature(
        self,
        *,
        feature_key: str,
        market_id: str,
        effective_date: date | str,
        as_of: date | str,
        value: float | None,
        confidence: float,
        inputs: dict[str, Any],
        builder_version: str = "1",
        meta: dict[str, Any] | None = None,
    ) -> str:
        inputs_hash = hashlib.sha256(
            json.dumps(inputs, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        self.conn.execute(
            """
            INSERT INTO signal_features (
                feature_key, market_id, effective_date, as_of, value, confidence,
                inputs_hash, builder_version, meta_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(feature_key, market_id, effective_date, as_of, builder_version)
            DO UPDATE SET
                value=excluded.value,
                confidence=excluded.confidence,
                inputs_hash=excluded.inputs_hash,
                meta_json=excluded.meta_json,
                created_at=datetime('now')
            """,
            (
                feature_key,
                market_id,
                _iso(effective_date),
                _iso(as_of),
                value,
                float(confidence),
                inputs_hash,
                builder_version,
                json.dumps(meta or {}),
            ),
        )
        self.conn.commit()
        return inputs_hash

    def read_feature(
        self,
        *,
        as_of: date | str,
        feature_key: str,
        market_id: str,
        effective_date: date | str,
        builder_version: str = "1",
    ) -> sqlite3.Row | None:
        """Feature built at a decision date <= as_of (feature.as_of is the build date)."""
        return self.conn.execute(
            """
            SELECT * FROM signal_features
            WHERE feature_key = ? AND market_id = ? AND effective_date = ?
              AND builder_version = ? AND as_of <= ?
            ORDER BY as_of DESC LIMIT 1
            """,
            (
                feature_key,
                market_id,
                _iso(effective_date),
                builder_version,
                _iso(as_of),
            ),
        ).fetchone()

    # ----------------------------------------------------------------- scores

    def write_score(
        self,
        *,
        signal_key: str,
        horizon_days: int,
        sample_size: int,
        information_coefficient: float | None,
        hit_rate: float | None,
        ic_ci_low: float | None,
        ic_ci_high: float | None,
        decision: str,
        notes: str = "",
        scored_at: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO signal_scores (
                signal_key, scored_at, horizon_days, sample_size,
                information_coefficient, hit_rate, ic_ci_low, ic_ci_high,
                decision, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(signal_key, scored_at, horizon_days) DO UPDATE SET
                sample_size=excluded.sample_size,
                information_coefficient=excluded.information_coefficient,
                hit_rate=excluded.hit_rate,
                ic_ci_low=excluded.ic_ci_low,
                ic_ci_high=excluded.ic_ci_high,
                decision=excluded.decision,
                notes=excluded.notes
            """,
            (
                signal_key,
                scored_at or _now_iso(),
                int(horizon_days),
                int(sample_size),
                information_coefficient,
                hit_rate,
                ic_ci_low,
                ic_ci_high,
                decision,
                notes,
            ),
        )
        self.conn.commit()
