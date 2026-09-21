-- Winter Park STR Pricing Engine — v2 schema
-- SQLite-compatible; Postgres-friendly types where noted.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id  TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    website    TEXT,
    timezone   TEXT NOT NULL DEFAULT 'America/Denver',
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO tenants (tenant_id, name, website)
VALUES ('mont_luxe_collection', 'Mont Luxe Collection', 'https://montluxecollection.com');

CREATE TABLE IF NOT EXISTS properties (
    tenant_id         TEXT NOT NULL DEFAULT 'mont_luxe_collection',
    property_id       TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    bedrooms          INTEGER NOT NULL,
    bathrooms         REAL NOT NULL,
    amenities         TEXT NOT NULL DEFAULT '[]',
    base_ceiling_rate REAL NOT NULL,
    min_floor_rate    REAL NOT NULL,
    max_ceiling_rate  REAL NOT NULL,
    luxury_tier       TEXT NOT NULL DEFAULT 'luxury',
    target_alos       REAL NOT NULL DEFAULT 3.0,
    timezone          TEXT NOT NULL DEFAULT 'America/Denver',
    pms_listing_id    TEXT,
    -- Portfolio owner slug from config/portfolio/mont_luxe.yaml (`northwoods`,
    -- `cloud9`). Scopes `wp-price recommend --owner` / `report --owner`.
    owner_id          TEXT,
    market_id         TEXT NOT NULL DEFAULT 'grand_home',
    -- Guesty `accommodates` / advertised sleeps. Used for display framing and
    -- group-size comp filters; never for RevPAN math.
    max_occupancy     INTEGER,
    airbnb_room_id    TEXT,          -- join key for scrape-only inventory
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comps (
    comp_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    bedrooms        INTEGER,
    bathrooms       REAL,
    -- Guest capacity when known (Airbnb/VRBO sleeps). Used for group-size tier filters.
    sleeps          INTEGER,
    amenities       TEXT NOT NULL DEFAULT '[]',
    notes           TEXT,
    source_url      TEXT,
    platform        TEXT NOT NULL DEFAULT 'airbnb',
    airbnb_room_id  TEXT,          -- join key for the market sweep
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_comps_room ON comps(airbnb_room_id);

CREATE TABLE IF NOT EXISTS comp_set_members (
    property_id TEXT NOT NULL REFERENCES properties(property_id),
    comp_id     TEXT NOT NULL REFERENCES comps(comp_id),
    PRIMARY KEY (property_id, comp_id)
);

-- Current state of the calendar. Overwritten on every ingest by design.
-- Historical shape of the calendar lives in pacing_snapshots.
CREATE TABLE IF NOT EXISTS nightly_inventory (
    property_id     TEXT NOT NULL REFERENCES properties(property_id),
    stay_date       TEXT NOT NULL,
    listed_price    REAL,
    booked_price    REAL,
    status          TEXT NOT NULL CHECK (status IN ('available', 'booked', 'blocked')),
    lead_time_days  INTEGER,
    day_of_week     INTEGER,
    channel         TEXT,
    reservation_id  TEXT,
    min_stay        INTEGER,
    -- Guesty confirmation timestamp (date the stay converted). Used for
    -- leak-free ceiling history: a booking confirmed after the decision date
    -- must not inform that decision. Calendar listed_price is NOT this.
    booked_at       TEXT,
    guest_count     INTEGER,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (property_id, stay_date)
);

-- Finished reservations as Guesty returned them. nightly_inventory is the
-- night-level view; this table keeps booking-date / guest-count / fare so a
-- retrospective can cut history at confirmation time rather than stay date.
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id  TEXT PRIMARY KEY,
    property_id     TEXT NOT NULL REFERENCES properties(property_id),
    listing_id      TEXT,
    check_in        TEXT NOT NULL,
    check_out       TEXT NOT NULL,
    nights          INTEGER,
    status          TEXT,
    source          TEXT,
    confirmed_at    TEXT,
    created_at_pms  TEXT,
    guest_count     INTEGER,
    fare_accommodation REAL,
    nightly_rate    REAL,
    raw_json        TEXT,
    synced_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reservations_property ON reservations(property_id, check_in);

CREATE TABLE IF NOT EXISTS sync_runs (
    run_id       TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at  TEXT,
    status       TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'ok', 'degraded', 'failed')),
    listings     INTEGER NOT NULL DEFAULT 0,
    calendar_nights INTEGER NOT NULL DEFAULT 0,
    reservations INTEGER NOT NULL DEFAULT 0,
    errors       TEXT NOT NULL DEFAULT '[]'
);

-- At-least-once Guesty deliveries are recorded before any refresh is queued.
-- The unique event id makes retries and duplicate webhook deliveries harmless.
CREATE TABLE IF NOT EXISTS pms_webhook_events (
    event_id     TEXT PRIMARY KEY,
    event_type   TEXT NOT NULL,
    listing_id   TEXT,
    start_date   TEXT,
    end_date     TEXT,
    payload_json TEXT NOT NULL,
    received_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_webhook_listing_dates
    ON pms_webhook_events(listing_id, start_date, end_date);

-- ---------------------------------------------------------------------------
-- Daily immutable capture of on-the-books state. THE highest-value table in the
-- system: it is the only source of pacing curves, and every day it is not
-- written is permanently lost. Turns ~1,460 property-nights/yr into ~40,000
-- (property, stay_date, days_out) observations.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pacing_snapshots (
    as_of           TEXT NOT NULL,   -- ISO date the observation was taken
    property_id     TEXT NOT NULL REFERENCES properties(property_id),
    stay_date       TEXT NOT NULL,
    days_out        INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('available', 'booked', 'blocked')),
    listed_price    REAL,
    min_stay        INTEGER,
    PRIMARY KEY (as_of, property_id, stay_date)
);

CREATE TABLE IF NOT EXISTS comp_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    comp_id         TEXT NOT NULL REFERENCES comps(comp_id),
    as_of           TEXT NOT NULL,
    stay_date       TEXT,
    listed_price    REAL,
    available       INTEGER,
    min_nights      INTEGER,
    -- CRITICAL: distinguishes "we looked and it was unavailable" from "we failed to
    -- look". A failed scrape that merely writes no row is indistinguishable from a
    -- fully-booked market, which is exactly the silent degradation the guardrails
    -- exist to prevent. Only 'ok' rows count toward comp coverage.
    scrape_status   TEXT NOT NULL DEFAULT 'ok'
        CHECK (scrape_status IN ('ok', 'unavailable', 'failed', 'blocked', 'stale')),
    window_nights   INTEGER,       -- stay length the quoted nightly rate came from
    source          TEXT NOT NULL DEFAULT 'manual',
    capture_method  TEXT NOT NULL DEFAULT 'operator_entry',
    run_id          TEXT,
    UNIQUE (comp_id, as_of, stay_date)
);

-- Full-market distribution per swept window. One search sweep returns every
-- bookable listing in the bounding box, so the market percentile is free and does
-- not depend on the curated comp set being complete.
CREATE TABLE IF NOT EXISTS market_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of           TEXT NOT NULL,
    stay_date       TEXT NOT NULL,
    window_nights   INTEGER NOT NULL,
    region          TEXT NOT NULL DEFAULT 'winter_park',
    listings        INTEGER NOT NULL,
    p25             REAL,
    p50             REAL,
    p75             REAL,
    p90             REAL,
    run_id          TEXT,
    UNIQUE (as_of, stay_date, region)
);

-- Per-run audit of the scraper. Without this, a silently degrading scraper looks
-- identical to a quiet market.
CREATE TABLE IF NOT EXISTS comp_scrape_runs (
    run_id            TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    started_at        TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at       TEXT,
    horizon_days      INTEGER,
    windows_attempted INTEGER NOT NULL DEFAULT 0,
    windows_ok        INTEGER NOT NULL DEFAULT 0,
    listings_seen     INTEGER NOT NULL DEFAULT 0,
    comps_matched     INTEGER NOT NULL DEFAULT 0,
    comps_expected    INTEGER NOT NULL DEFAULT 0,
    observations      INTEGER NOT NULL DEFAULT 0,
    rejected          INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'ok', 'degraded', 'failed')),
    errors            TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS demand_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_date     TEXT NOT NULL,
    region          TEXT NOT NULL DEFAULT 'winter_park',
    event_name      TEXT NOT NULL,
    signal_strength REAL NOT NULL CHECK (signal_strength >= 0 AND signal_strength <= 1),
    source          TEXT NOT NULL DEFAULT 'manual',
    UNIQUE (signal_date, region, event_name)
);

CREATE TABLE IF NOT EXISTS booking_inquiries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id     TEXT NOT NULL REFERENCES properties(property_id),
    inquiry_date    TEXT NOT NULL,
    stay_date       TEXT,
    inquiry_count   INTEGER NOT NULL DEFAULT 1,
    quote_shown     REAL,
    converted       INTEGER NOT NULL DEFAULT 0,
    external_id     TEXT,
    UNIQUE (property_id, inquiry_date, stay_date, external_id)
);

CREATE TABLE IF NOT EXISTS price_recommendations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    property_id         TEXT NOT NULL REFERENCES properties(property_id),
    stay_date           TEXT NOT NULL,
    recommended_price   REAL NOT NULL,
    ceiling_price       REAL NOT NULL,
    floor_price         REAL NOT NULL,
    listed_price_at_run REAL,
    expected_book_prob  REAL,
    expected_revpan     REAL,
    ceiling_confidence  REAL,
    autonomy_level      TEXT NOT NULL DEFAULT 'suggest'
        CHECK (autonomy_level IN ('watch', 'suggest', 'handle', 'escalate')),
    guardrail_action    TEXT,          -- null = unmodified; else why it was clamped/blocked
    reasons             TEXT NOT NULL DEFAULT '[]',
    rule_version        TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    inputs_hash         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'suggested'
        CHECK (status IN ('suggested', 'accepted', 'overridden', 'blocked')),
    -- Engine-owned LOS decision (policy table and/or gap override). Null = no change.
    recommended_min_stay INTEGER,
    min_stay_source      TEXT,         -- policy | gap_override | inventory | none
    -- Display-only framing: recommended_price / max_occupancy. Never used in RevPAN.
    per_person_nightly   REAL,
    -- Owner-facing band around recommended_price. Derived from ceiling confidence
    -- and clipped to search bounds — not a statistical interval. See src/explain/present.py.
    range_low            REAL,
    range_high           REAL,
    evidence_count       INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    -- One recommendation per property/night per run. The v1 constraint included
    -- created_at (second resolution) and therefore deduplicated nothing.
    UNIQUE (run_id, property_id, stay_date)
);

-- Immutable audit of every rate actually written to a channel.
CREATE TABLE IF NOT EXISTS rate_changes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER REFERENCES price_recommendations(id),
    property_id       TEXT NOT NULL,
    stay_date         TEXT NOT NULL,
    old_price         REAL,
    new_price         REAL NOT NULL,
    actor             TEXT NOT NULL,   -- 'engine' | 'operator' | adapter name
    autonomy_level    TEXT NOT NULL,
    result            TEXT NOT NULL DEFAULT 'pending'
        CHECK (result IN ('pending', 'applied', 'failed', 'dry_run')),
    error             TEXT,
    -- Denormalized from the Recommendation at write time. Do not rely on joining
    -- price_recommendations: recommendation_id can miss and become NULL.
    rule_version      TEXT,
    model_version     TEXT,
    inputs_hash       TEXT,
    request_id        TEXT,
    pushed_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Result of the pre-push data-health gate for each run.
CREATE TABLE IF NOT EXISTS data_health_runs (
    run_id            TEXT PRIMARY KEY,
    as_of             TEXT NOT NULL DEFAULT (datetime('now')),
    pms_age_hours     REAL,
    comp_age_hours    REAL,
    comp_coverage     REAL,
    pacing_days       INTEGER,
    granted_level     TEXT NOT NULL,
    failures          TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS recommendation_outcomes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id   INTEGER NOT NULL REFERENCES price_recommendations(id),
    property_id         TEXT NOT NULL,
    stay_date           TEXT NOT NULL,
    final_listed_price  REAL,
    price_was_applied   INTEGER NOT NULL DEFAULT 0,  -- did the rec actually reach the channel?
    booked              INTEGER NOT NULL DEFAULT 0,
    booked_price        REAL,
    revenue             REAL NOT NULL DEFAULT 0,
    evaluated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (recommendation_id)
);

-- ---------------------------------------------------------------------------
-- Pfeifer Optimization — markets + typed observations. Agents write observations;
-- deterministic feature builders write features; only the guarded engine prices.
-- Every observation stores observed_at separately from effective_date.
-- Reads MUST filter observed_at <= as_of (enforced in src/signals/store.py).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS markets (
    market_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    ring            TEXT NOT NULL
        CHECK (ring IN ('home', 'valley', 'substitute', 'watch')),
    county          TEXT,
    region_legacy   TEXT,          -- maps old region strings (e.g. winter_park)
    bbox_ne_lat     REAL,
    bbox_ne_lng     REAL,
    bbox_sw_lat     REAL,
    bbox_sw_lng     REAL,
    centroid_lat    REAL,
    centroid_lng    REAL,
    snotel_stations TEXT NOT NULL DEFAULT '[]',  -- JSON list of triplets
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signal_definitions (
    signal_key      TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    unit            TEXT NOT NULL,
    cadence         TEXT NOT NULL,
    source          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'experimental'
        CHECK (status IN ('experimental', 'shadow', 'active', 'deprecated')),
    schema_version  TEXT NOT NULL DEFAULT '1',
    description     TEXT,
    value_min       REAL,
    value_max       REAL,
    collector       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signal_runs (
    run_id          TEXT PRIMARY KEY,
    collector       TEXT NOT NULL,
    market_id       TEXT REFERENCES markets(market_id),
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at     TEXT,
    as_of           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'ok', 'degraded', 'failed')),
    observations    INTEGER NOT NULL DEFAULT 0,
    rejected        INTEGER NOT NULL DEFAULT 0,
    errors          TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS signal_observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_key      TEXT NOT NULL REFERENCES signal_definitions(signal_key),
    market_id       TEXT NOT NULL REFERENCES markets(market_id),
    observed_at     TEXT NOT NULL,   -- when we learned it (leak-free constraint)
    effective_date  TEXT NOT NULL,   -- the date the value describes
    horizon_days    INTEGER NOT NULL DEFAULT 0,
    value           REAL,
    confidence      REAL NOT NULL DEFAULT 1.0
        CHECK (confidence >= 0 AND confidence <= 1),
    quality         TEXT NOT NULL DEFAULT 'ok'
        CHECK (quality IN ('ok', 'unavailable', 'failed', 'blocked', 'stale')),
    provenance_url  TEXT,
    run_id          TEXT REFERENCES signal_runs(run_id),
    meta_json       TEXT NOT NULL DEFAULT '{}',
    UNIQUE (signal_key, market_id, observed_at, effective_date, horizon_days)
);
CREATE INDEX IF NOT EXISTS idx_sig_obs_asof
    ON signal_observations(signal_key, market_id, effective_date, observed_at);
CREATE INDEX IF NOT EXISTS idx_sig_obs_observed ON signal_observations(observed_at);

-- ---------------------------------------------------------------------------
-- Winter Park resort intelligence — daily immutable lift/trail archive.
-- Skipped days are permanently lost (same discipline as pacing_snapshots).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resort_snapshots (
    as_of           TEXT NOT NULL,
    market_id       TEXT NOT NULL REFERENCES markets(market_id),
    payload_json    TEXT NOT NULL,
    source_url      TEXT,
    lift_open       INTEGER,
    lift_total      INTEGER,
    trail_open      INTEGER,
    trail_total     INTEGER,
    PRIMARY KEY (as_of, market_id)
);
CREATE INDEX IF NOT EXISTS idx_resort_snap_asof ON resort_snapshots(as_of);

-- Curated historical facts APIs cannot backfill (wind holds, terrain opens, etc.)
CREATE TABLE IF NOT EXISTS resort_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resort_id       TEXT NOT NULL DEFAULT 'winter_park',
    event_date      TEXT NOT NULL,
    event_type      TEXT NOT NULL
        CHECK (event_type IN (
            'closure', 'wind_hold', 'terrain_open', 'ikon_blackout',
            'access_closure', 'season_open', 'season_close'
        )),
    entity_name     TEXT,
    notes           TEXT,
    source_url      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_resort_events_date ON resort_events(resort_id, event_date);

-- Monthly / seasonal reference stats (OnTheSnow norms, opening curves).
CREATE TABLE IF NOT EXISTS resort_season_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resort_id       TEXT NOT NULL DEFAULT 'winter_park',
    stat_key        TEXT NOT NULL,
    month           INTEGER,
    season          TEXT,
    value           REAL NOT NULL,
    unit            TEXT NOT NULL,
    source          TEXT,
    UNIQUE (resort_id, stat_key, month, season)
);

CREATE TABLE IF NOT EXISTS signal_features (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_key     TEXT NOT NULL,
    market_id       TEXT NOT NULL REFERENCES markets(market_id),
    effective_date  TEXT NOT NULL,
    as_of           TEXT NOT NULL,   -- decision date used to build this feature
    value           REAL,
    confidence      REAL NOT NULL DEFAULT 1.0,
    inputs_hash     TEXT NOT NULL,
    builder_version TEXT NOT NULL DEFAULT '1',
    meta_json       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (feature_key, market_id, effective_date, as_of, builder_version)
);

CREATE TABLE IF NOT EXISTS signal_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_key      TEXT NOT NULL REFERENCES signal_definitions(signal_key),
    scored_at       TEXT NOT NULL DEFAULT (datetime('now')),
    horizon_days    INTEGER NOT NULL,
    sample_size     INTEGER NOT NULL,
    information_coefficient REAL,
    hit_rate        REAL,
    ic_ci_low       REAL,
    ic_ci_high      REAL,
    decision        TEXT NOT NULL
        CHECK (decision IN ('promote', 'hold', 'demote', 'insufficient')),
    notes           TEXT,
    UNIQUE (signal_key, scored_at, horizon_days)
);

-- market_id column on legacy region tables (additive; region string kept for shim)
-- SQLite cannot ADD COLUMN IF NOT EXISTS portably; init_db applies migrations.

CREATE INDEX IF NOT EXISTS idx_properties_owner  ON properties(owner_id);
CREATE INDEX IF NOT EXISTS idx_inventory_date    ON nightly_inventory(stay_date);
CREATE INDEX IF NOT EXISTS idx_inventory_status  ON nightly_inventory(status);
CREATE INDEX IF NOT EXISTS idx_pacing_stay       ON pacing_snapshots(property_id, stay_date);
CREATE INDEX IF NOT EXISTS idx_pacing_asof       ON pacing_snapshots(as_of);
CREATE INDEX IF NOT EXISTS idx_comp_snap_stay    ON comp_snapshots(stay_date);
CREATE INDEX IF NOT EXISTS idx_comp_snap_status  ON comp_snapshots(scrape_status);
CREATE INDEX IF NOT EXISTS idx_market_stay       ON market_snapshots(stay_date);
CREATE INDEX IF NOT EXISTS idx_demand_date       ON demand_signals(signal_date);
CREATE INDEX IF NOT EXISTS idx_recs_prop_date    ON price_recommendations(property_id, stay_date);
CREATE INDEX IF NOT EXISTS idx_rate_changes_pd   ON rate_changes(property_id, stay_date);
CREATE INDEX IF NOT EXISTS idx_outcomes_prop_date ON recommendation_outcomes(property_id, stay_date);
