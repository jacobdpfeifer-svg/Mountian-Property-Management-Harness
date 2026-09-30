-- Operations layer. Read-only with respect to Guesty: nothing here writes rates,
-- availability, or reservations. See docs/rules/OPERATIONS.md.

-- One row per profile version. Version is the content hash of the YAML block,
-- so re-loading an unchanged file is a no-op.
CREATE TABLE IF NOT EXISTS property_operations_profile (
    property_id             TEXT NOT NULL,
    version                 TEXT NOT NULL,
    checkout_time           TEXT NOT NULL,
    checkin_time            TEXT NOT NULL,
    base_clean_minutes      INTEGER NOT NULL,
    inspection_minutes      INTEGER NOT NULL DEFAULT 0,
    laundry_mode            TEXT NOT NULL DEFAULT 'onsite',
    laundry_minutes         INTEGER NOT NULL DEFAULT 0,
    hot_tub_reset_minutes   INTEGER NOT NULL DEFAULT 0,
    snow_clearance_required INTEGER NOT NULL DEFAULT 0,
    snow_clearance_minutes  INTEGER NOT NULL DEFAULT 0,
    access_zone             TEXT NOT NULL,
    travel_minutes          INTEGER NOT NULL DEFAULT 0,
    crew_size               INTEGER NOT NULL DEFAULT 1,
    labor_rate_per_hour     REAL,
    fixed_cost_per_turn     REAL NOT NULL DEFAULT 0,
    laundry_cost_per_turn   REAL NOT NULL DEFAULT 0,
    hot_tub_cost_per_turn   REAL NOT NULL DEFAULT 0,
    snow_cost_per_visit     REAL NOT NULL DEFAULT 0,
    basis                   TEXT NOT NULL DEFAULT 'estimate'
        CHECK (basis IN ('estimate', 'observed', 'operator_confirmed')),
    loaded_at               TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (property_id, version)
);
CREATE INDEX IF NOT EXISTS idx_ops_profile_loaded
    ON property_operations_profile(property_id, loaded_at);

CREATE TABLE IF NOT EXISTS ops_import_runs (
    run_id      TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'ok', 'partial', 'failed', 'unconfigured')),
    rows_in     INTEGER NOT NULL DEFAULT 0,
    accepted    INTEGER NOT NULL DEFAULT 0,
    rejected    INTEGER NOT NULL DEFAULT 0,
    errors      TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS operations_capacity_snapshots (
    as_of                    TEXT NOT NULL,
    service_date             TEXT NOT NULL,
    access_zone              TEXT NOT NULL,
    service_type             TEXT NOT NULL DEFAULT 'turnover',
    available_worker_minutes REAL NOT NULL,
    committed_worker_minutes REAL NOT NULL DEFAULT 0,
    source                   TEXT NOT NULL,
    confidence               REAL NOT NULL DEFAULT 0.5
        CHECK (confidence >= 0 AND confidence <= 1),
    import_run_id            TEXT,
    PRIMARY KEY (as_of, service_date, access_zone, service_type, source)
);

CREATE TABLE IF NOT EXISTS turnover_outcomes (
    outcome_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id             TEXT,
    property_id         TEXT NOT NULL,
    service_date        TEXT NOT NULL,
    service_type        TEXT NOT NULL DEFAULT 'turnover',
    scheduled_start     TEXT,
    completed_at        TEXT,
    required_minutes    REAL,
    actual_minutes      REAL,
    cost                REAL,
    qa_pass             INTEGER,
    rework_minutes      REAL,
    late_ready_minutes  REAL,
    assignee_ref        TEXT,
    source              TEXT NOT NULL,
    source_task_id      TEXT NOT NULL,
    import_run_id       TEXT,
    raw_json            TEXT,
    imported_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source, source_task_id)
);
CREATE INDEX IF NOT EXISTS idx_turnover_outcomes_property
    ON turnover_outcomes(property_id, service_date);

CREATE TABLE IF NOT EXISTS asset_health_events (
    event_id       TEXT PRIMARY KEY,
    property_id    TEXT NOT NULL,
    system_type    TEXT NOT NULL
        CHECK (system_type IN ('heat', 'water', 'septic', 'spa', 'lock', 'snow_access',
                               'power', 'propane', 'co_safety', 'fireplace', 'wildfire',
                               'other')),
    observed_at    TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to   TEXT,
    severity       TEXT NOT NULL CHECK (severity IN ('info', 'warn', 'critical')),
    source_type    TEXT NOT NULL
        CHECK (source_type IN ('sensor', 'guest', 'cleaner', 'vendor', 'manual', 'signal')),
    source_ref     TEXT,
    reading_json   TEXT NOT NULL DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    verified_by    TEXT,
    resolved_at    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_asset_events_property
    ON asset_health_events(property_id, observed_at);

-- Append-only. The current state is the latest row; it is never stored twice.
CREATE TABLE IF NOT EXISTS readiness_transitions (
    transition_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id       TEXT NOT NULL,
    from_state        TEXT NOT NULL,
    to_state          TEXT NOT NULL,
    at                TEXT NOT NULL,
    effective_from    TEXT NOT NULL,
    effective_to      TEXT,
    evidence_event_id TEXT NOT NULL REFERENCES asset_health_events(event_id),
    actor             TEXT NOT NULL,
    note              TEXT
);
CREATE INDEX IF NOT EXISTS idx_readiness_property
    ON readiness_transitions(property_id, at, transition_id);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id    TEXT PRIMARY KEY,
    incident_type  TEXT NOT NULL,
    market_id      TEXT NOT NULL,
    detected_at    TEXT NOT NULL,
    window_start   TEXT NOT NULL,
    window_end     TEXT NOT NULL,
    severity       TEXT NOT NULL,
    signal_key     TEXT NOT NULL,
    signal_value   REAL,
    threshold      REAL,
    status         TEXT NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'acknowledged', 'dismissed', 'closed')),
    affected_json  TEXT NOT NULL DEFAULT '{}',
    actions_json   TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS incident_actions (
    action_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  TEXT NOT NULL REFERENCES incidents(incident_id),
    action_code  TEXT NOT NULL,
    status       TEXT NOT NULL
        CHECK (status IN ('approved', 'rejected', 'executed', 'failed', 'outcome')),
    actor        TEXT NOT NULL,
    at           TEXT NOT NULL DEFAULT (datetime('now')),
    payload_json TEXT NOT NULL DEFAULT '{}',
    output_ref   TEXT,
    outcome      TEXT
);

CREATE TABLE IF NOT EXISTS property_credentials (
    credential_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id         TEXT NOT NULL,
    jurisdiction        TEXT NOT NULL,
    credential_type     TEXT NOT NULL,
    identifier          TEXT,
    permitted_occupancy INTEGER,
    issued_at           TEXT,
    expires_at          TEXT,
    evidence_ref        TEXT,
    evidence_hash       TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified', 'verified', 'rejected')),
    verified_at         TEXT,
    verified_by         TEXT,
    rule_pack_version   TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (property_id, credential_type, identifier)
);

CREATE TABLE IF NOT EXISTS owner_ledger_entries (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id     TEXT NOT NULL,
    property_id  TEXT,
    entry_date   TEXT NOT NULL,
    category     TEXT NOT NULL
        CHECK (category IN ('maintenance', 'reimbursable', 'supplies', 'preventive', 'other')),
    amount       REAL NOT NULL,
    memo         TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'csv',
    evidence_ref TEXT,
    imported_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source, owner_id, property_id, entry_date, category, amount, memo)
);
