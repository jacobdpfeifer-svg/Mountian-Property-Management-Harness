-- 0005_review: daily decision-review queue and immutable, attributable actions.
CREATE TABLE IF NOT EXISTS review_item (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_key        TEXT NOT NULL UNIQUE,
    property_id         TEXT NOT NULL,
    stay_date           TEXT NOT NULL,
    current_rate        REAL,
    proposed_rate       REAL NOT NULL,
    all_in_price        REAL,
    expected_owner_net  REAL,
    owner_net_basis     TEXT NOT NULL,        -- actual_terms | assumed_terms | unavailable
    freshness_json      TEXT NOT NULL,
    confidence          REAL,
    reasons_json        TEXT NOT NULL,
    guardrails_json     TEXT NOT NULL,
    readiness           TEXT NOT NULL,
    assignment_arm      TEXT NOT NULL,        -- treatment | control | not_assigned
    expires_at          TEXT NOT NULL,
    created_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_action (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES review_item(id),
    action          TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'edit')),
    actor           TEXT NOT NULL,
    role            TEXT NOT NULL,
    decided_price   REAL,                     -- NULL for reject
    reason          TEXT NOT NULL,
    acted_at        TEXT NOT NULL,
    prev_sha256     TEXT NOT NULL,
    receipt_sha256  TEXT NOT NULL UNIQUE,
    UNIQUE (item_id)                          -- one terminal decision per item
);
CREATE TRIGGER IF NOT EXISTS review_item_no_update BEFORE UPDATE ON review_item
    BEGIN SELECT RAISE(ABORT, 'append-only: update on review_item refused'); END;
CREATE TRIGGER IF NOT EXISTS review_item_no_delete BEFORE DELETE ON review_item
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on review_item refused'); END;
CREATE TRIGGER IF NOT EXISTS review_action_no_update BEFORE UPDATE ON review_action
    BEGIN SELECT RAISE(ABORT, 'append-only: update on review_action refused'); END;
CREATE TRIGGER IF NOT EXISTS review_action_no_delete BEFORE DELETE ON review_action
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on review_action refused'); END;
