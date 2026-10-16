-- 0001_data_spine: versioned, append-only facts for decision -> outcome lineage.
--
-- Every fact row carries the same lineage columns:
--   entity_key          stable business key (pseudonymous; never a guest name/email)
--   version_no          1, 2, ... per entity_key
--   supersedes_id       the row this version corrects (NULL for version 1)
--   correction_reason   why the new version exists (NULL for version 1)
--   source_system       e.g. guesty, airbnb_payout, owner_statement, scrape, fixture
--   source_record_id    the source's own id for the record, when it has one
--   source_hash         sha256 of the canonical contract payload (idempotency)
--   schema_version      contract version the row was validated against
--   source_updated_at   when the source says the record last changed (UTC ISO)
--   observed_at         when we read it (UTC ISO)
--   ingested_at         when it was written here
--   batch_id            spine_source_batch row that delivered it
--
-- Rows are never updated or deleted (triggers below). A correction is a new row
-- whose supersedes_id points at the prior version. "Current" = not superseded.

CREATE TABLE IF NOT EXISTS spine_source_batch (
    batch_id        TEXT PRIMARY KEY,
    contract_name   TEXT NOT NULL,
    schema_version  TEXT NOT NULL,
    source_system   TEXT NOT NULL,
    received_at     TEXT NOT NULL,
    record_count    INTEGER NOT NULL,
    accepted        INTEGER NOT NULL,
    duplicates      INTEGER NOT NULL,
    quarantined     INTEGER NOT NULL
);

-- Rejected records. The payload is stored only after the contract strips every
-- field it does not declare, so PII never lands here either.
CREATE TABLE IF NOT EXISTS spine_quarantine (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    contract_name   TEXT NOT NULL,
    entity_key      TEXT,
    reason_codes    TEXT NOT NULL,          -- JSON list, e.g. ["AMBIGUOUS_PRICE_BASIS"]
    detail          TEXT NOT NULL,
    payload_json    TEXT NOT NULL,          -- contract fields only
    source_hash     TEXT NOT NULL,
    quarantined_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spine_quarantine_contract
    ON spine_quarantine(contract_name, quarantined_at);

CREATE TABLE IF NOT EXISTS fact_price_decision (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key         TEXT NOT NULL,       -- decision id
    version_no         INTEGER NOT NULL,
    supersedes_id      INTEGER REFERENCES fact_price_decision(id),
    correction_reason  TEXT,
    source_system      TEXT NOT NULL,
    source_record_id   TEXT,
    source_hash        TEXT NOT NULL,
    schema_version     TEXT NOT NULL,
    source_updated_at  TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    batch_id           TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    property_id        TEXT NOT NULL,
    stay_date          TEXT NOT NULL,
    run_id             TEXT,
    policy_hash        TEXT NOT NULL,
    calibration_hash   TEXT,
    data_hash          TEXT NOT NULL,
    model_version      TEXT NOT NULL,
    price_basis        TEXT NOT NULL,
    currency           TEXT NOT NULL,
    current_price      REAL,
    recommended_price  REAL NOT NULL,
    human_decision     TEXT NOT NULL,       -- pending | approved | rejected | edited | not_required
    human_price        REAL,
    applied_price      REAL,
    autonomy_level     TEXT NOT NULL,
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);

CREATE TABLE IF NOT EXISTS fact_reservation_version (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key         TEXT NOT NULL,       -- pseudonymous reservation key
    version_no         INTEGER NOT NULL,
    supersedes_id      INTEGER REFERENCES fact_reservation_version(id),
    correction_reason  TEXT,
    source_system      TEXT NOT NULL,
    source_record_id   TEXT,
    source_hash        TEXT NOT NULL,
    schema_version     TEXT NOT NULL,
    source_updated_at  TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    batch_id           TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    property_id        TEXT NOT NULL,
    channel            TEXT NOT NULL,
    status             TEXT NOT NULL,       -- confirmed | modified | cancelled
    check_in           TEXT NOT NULL,
    check_out          TEXT NOT NULL,
    nights             INTEGER NOT NULL,
    booked_at          TEXT NOT NULL,
    price_basis        TEXT NOT NULL,
    currency           TEXT NOT NULL,
    gross_lodging      REAL NOT NULL,
    guest_fees         REAL NOT NULL,
    decision_key       TEXT,                -- fact_price_decision.entity_key, when attributable
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);

-- Night rows are derived from one reservation version at ingest and inherit its
-- lineage through reservation_version_id.
CREATE TABLE IF NOT EXISTS fact_reservation_night (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_version_id  INTEGER NOT NULL REFERENCES fact_reservation_version(id),
    property_id             TEXT NOT NULL,
    stay_date               TEXT NOT NULL,
    nightly_lodging         REAL NOT NULL,
    price_basis             TEXT NOT NULL,
    UNIQUE (reservation_version_id, stay_date)
);

CREATE TABLE IF NOT EXISTS fact_calendar_observation (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key         TEXT NOT NULL,       -- property_id|stay_date
    version_no         INTEGER NOT NULL,
    supersedes_id      INTEGER REFERENCES fact_calendar_observation(id),
    correction_reason  TEXT,
    source_system      TEXT NOT NULL,
    source_record_id   TEXT,
    source_hash        TEXT NOT NULL,
    schema_version     TEXT NOT NULL,
    source_updated_at  TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    batch_id           TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    property_id        TEXT NOT NULL,
    stay_date          TEXT NOT NULL,
    status             TEXT NOT NULL,       -- available | booked | blocked
    listed_price       REAL,
    min_stay           INTEGER,
    price_basis        TEXT NOT NULL,
    currency           TEXT NOT NULL,
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);

CREATE TABLE IF NOT EXISTS fact_financial_ledger (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key         TEXT NOT NULL,       -- ledger entry id
    version_no         INTEGER NOT NULL,
    supersedes_id      INTEGER REFERENCES fact_financial_ledger(id),
    correction_reason  TEXT,
    source_system      TEXT NOT NULL,
    source_record_id   TEXT,
    source_hash        TEXT NOT NULL,
    schema_version     TEXT NOT NULL,
    source_updated_at  TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    batch_id           TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    reservation_key    TEXT,                -- NULL for property-level costs
    property_id        TEXT NOT NULL,
    channel            TEXT NOT NULL,
    entry_type         TEXT NOT NULL,
    direction          TEXT NOT NULL,       -- credit (to owner economics) | debit
    amount             REAL NOT NULL,       -- always >= 0; sign lives in direction
    currency           TEXT NOT NULL,
    basis              TEXT NOT NULL,       -- actual | assumed
    settlement_state   TEXT NOT NULL,       -- pending | settled | reversed
    settled_at         TEXT,
    statement_key      TEXT,
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);
CREATE INDEX IF NOT EXISTS idx_ledger_reservation ON fact_financial_ledger(reservation_key);
CREATE INDEX IF NOT EXISTS idx_ledger_statement ON fact_financial_ledger(statement_key);

CREATE TABLE IF NOT EXISTS fact_owner_statement (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key          TEXT NOT NULL,      -- statement id
    version_no          INTEGER NOT NULL,
    supersedes_id       INTEGER REFERENCES fact_owner_statement(id),
    correction_reason   TEXT,
    source_system       TEXT NOT NULL,
    source_record_id    TEXT,
    source_hash         TEXT NOT NULL,
    schema_version      TEXT NOT NULL,
    source_updated_at   TEXT NOT NULL,
    observed_at         TEXT NOT NULL,
    ingested_at         TEXT NOT NULL,
    batch_id            TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    owner_id            TEXT NOT NULL,
    property_id         TEXT NOT NULL,
    period_start        TEXT NOT NULL,
    period_end          TEXT NOT NULL,
    reported_owner_net  REAL NOT NULL,
    currency            TEXT NOT NULL,
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);

CREATE TABLE IF NOT EXISTS fact_market_observation (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key         TEXT NOT NULL,       -- comp_key|stay_date|los|observed_at
    version_no         INTEGER NOT NULL,
    supersedes_id      INTEGER REFERENCES fact_market_observation(id),
    correction_reason  TEXT,
    source_system      TEXT NOT NULL,
    source_record_id   TEXT,
    source_hash        TEXT NOT NULL,
    schema_version     TEXT NOT NULL,
    source_updated_at  TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    batch_id           TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    comp_key           TEXT NOT NULL,
    stay_date          TEXT NOT NULL,
    los                INTEGER NOT NULL,
    guests             INTEGER,
    price              REAL NOT NULL,
    price_basis        TEXT NOT NULL,
    currency           TEXT NOT NULL,
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);

CREATE TABLE IF NOT EXISTS fact_ops_task (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key         TEXT NOT NULL,       -- vendor task id
    version_no         INTEGER NOT NULL,
    supersedes_id      INTEGER REFERENCES fact_ops_task(id),
    correction_reason  TEXT,
    source_system      TEXT NOT NULL,
    source_record_id   TEXT,
    source_hash        TEXT NOT NULL,
    schema_version     TEXT NOT NULL,
    source_updated_at  TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    batch_id           TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    property_id        TEXT NOT NULL,
    task_type          TEXT NOT NULL,       -- turn | inspection | maintenance | incident
    service_date       TEXT NOT NULL,
    status             TEXT NOT NULL,       -- scheduled | in_progress | completed | failed | cancelled
    vendor             TEXT NOT NULL,
    cost               REAL,
    currency           TEXT NOT NULL,
    reservation_key    TEXT,
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);

-- Constraints may only restrict a night (never make one bookable): effect is
-- fixed to 'restrict' by CHECK and by the contract.
CREATE TABLE IF NOT EXISTS dim_listing_constraint (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_key         TEXT NOT NULL,
    version_no         INTEGER NOT NULL,
    supersedes_id      INTEGER REFERENCES dim_listing_constraint(id),
    correction_reason  TEXT,
    source_system      TEXT NOT NULL,
    source_record_id   TEXT,
    source_hash        TEXT NOT NULL,
    schema_version     TEXT NOT NULL,
    source_updated_at  TEXT NOT NULL,
    observed_at        TEXT NOT NULL,
    ingested_at        TEXT NOT NULL,
    batch_id           TEXT NOT NULL REFERENCES spine_source_batch(batch_id),
    property_id        TEXT NOT NULL,
    constraint_type    TEXT NOT NULL,       -- owner_block | maintenance | capacity | emergency | min_stay_floor
    start_date         TEXT NOT NULL,
    end_date           TEXT NOT NULL,       -- inclusive
    effect             TEXT NOT NULL CHECK (effect = 'restrict'),
    active             INTEGER NOT NULL,    -- 1 active, 0 lifted (a lift is a new version)
    UNIQUE (entity_key, version_no),
    UNIQUE (source_system, source_hash)
);
