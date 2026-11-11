-- 0007_shadow_night: one append-only row per property, as-of date, and stay date.
-- Shadow records what was listed and what the engine would have recommended.
-- It does not store a rate write. adr and revpan stay null until a later outcome
-- says the night actually sold; forecast_revpan is the engine's expectation.
CREATE TABLE IF NOT EXISTS shadow_night (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of                   TEXT NOT NULL,
    property_id             TEXT NOT NULL,
    stay_date               TEXT NOT NULL,
    decision_key            TEXT NOT NULL,
    listed_rate             REAL,
    min_stay                INTEGER,
    availability            TEXT NOT NULL,
    recommended_price       REAL,
    reasons_json            TEXT NOT NULL,
    health_level            TEXT NOT NULL,
    autonomy_level          TEXT NOT NULL,
    comp_age_hours          REAL,
    comp_coverage           REAL,
    price_basis_confidence  TEXT NOT NULL,
    lead_time_days          INTEGER,
    length_of_stay          INTEGER,
    channel                 TEXT,
    adr                     REAL,
    revpan                  REAL,
    forecast_revpan         REAL,
    owner_net_total         REAL,
    owner_net_status        TEXT,
    weak_ceiling            INTEGER NOT NULL,
    price_distance          REAL,
    created_at              TEXT NOT NULL,
    UNIQUE (as_of, property_id, stay_date)
);
CREATE TRIGGER IF NOT EXISTS shadow_night_no_update BEFORE UPDATE ON shadow_night
    BEGIN SELECT RAISE(ABORT, 'append-only: update on shadow_night refused'); END;
CREATE TRIGGER IF NOT EXISTS shadow_night_no_delete BEFORE DELETE ON shadow_night
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on shadow_night refused'); END;
