-- 0008_shadow_outcome_metrics: append-only, source-fingerprinted outcome observations.
-- `shadow_outcome` preserves the first observed calendar outcome. This ledger
-- holds every distinct later observation, including settlement that arrives
-- after a stay. Owner net is explicitly per stay-night: recording a whole
-- reservation total on every night would overstate a multi-night stay.
CREATE TABLE IF NOT EXISTS shadow_outcome_observation (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_key       TEXT NOT NULL REFERENCES review_item(decision_key),
    reservation_key    TEXT,
    observed_at        TEXT NOT NULL,
    night_status       TEXT NOT NULL,
    actual_adr         REAL,
    actual_revpan      REAL,
    settled_owner_net_per_night REAL,
    owner_net_status   TEXT,
    source_system      TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    UNIQUE (decision_key, source_fingerprint)
);
CREATE TRIGGER IF NOT EXISTS shadow_outcome_observation_no_update BEFORE UPDATE ON shadow_outcome_observation
    BEGIN SELECT RAISE(ABORT, 'append-only: update on shadow_outcome_observation refused'); END;
CREATE TRIGGER IF NOT EXISTS shadow_outcome_observation_no_delete BEFORE DELETE ON shadow_outcome_observation
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on shadow_outcome_observation refused'); END;
