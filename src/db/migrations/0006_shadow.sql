-- 0006_shadow: read-only daily shadow runs and later outcome capture (workstream 6).
-- Append-only. A shadow run never writes a rate; `rate_writes` records the count of
-- Guesty writes seen in this database at run time and must be 0.
CREATE TABLE IF NOT EXISTS shadow_run (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of           TEXT NOT NULL,
    property_id     TEXT NOT NULL,
    nights          INTEGER NOT NULL,
    health_level    TEXT NOT NULL,          -- granted autonomy level from data health
    health_json     TEXT NOT NULL,
    anchored_share  REAL,                   -- share of nights with a market anchor
    rate_writes     INTEGER NOT NULL CHECK (rate_writes = 0),
    code_sha256     TEXT NOT NULL,
    policy_sha256   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE (as_of, property_id)
);
CREATE TABLE IF NOT EXISTS shadow_outcome (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_key    TEXT NOT NULL REFERENCES review_item(decision_key),
    stay_date       TEXT NOT NULL,
    captured_at     TEXT NOT NULL,
    night_status    TEXT NOT NULL,          -- booked | available | blocked | unknown
    sold_price      REAL,                   -- nightly price the night sold at, if sold
    reservation_key TEXT,
    owner_net_status TEXT,                  -- spine owner-net status for that stay, if known
    UNIQUE (decision_key)
);
CREATE TRIGGER IF NOT EXISTS shadow_run_no_update BEFORE UPDATE ON shadow_run
    BEGIN SELECT RAISE(ABORT, 'append-only: update on shadow_run refused'); END;
CREATE TRIGGER IF NOT EXISTS shadow_run_no_delete BEFORE DELETE ON shadow_run
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on shadow_run refused'); END;
CREATE TRIGGER IF NOT EXISTS shadow_outcome_no_update BEFORE UPDATE ON shadow_outcome
    BEGIN SELECT RAISE(ABORT, 'append-only: update on shadow_outcome refused'); END;
CREATE TRIGGER IF NOT EXISTS shadow_outcome_no_delete BEFORE DELETE ON shadow_outcome
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on shadow_outcome refused'); END;
