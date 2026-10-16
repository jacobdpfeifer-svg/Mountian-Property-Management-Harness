-- 0004_webhook_ingress: verified receipts, dead letters, and refetch requests.
-- All three are append-only; a refetch's completion is a separate row.
CREATE TABLE IF NOT EXISTS webhook_receipt (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id     TEXT NOT NULL UNIQUE,
    signed_at       TEXT NOT NULL,
    received_at     TEXT NOT NULL,
    body_sha256     TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    property_id     TEXT,               -- NULL when out of scope (quarantined)
    scope_status    TEXT NOT NULL CHECK (scope_status IN ('in_scope', 'quarantined', 'not_listing_scoped')),
    payload_json    TEXT NOT NULL       -- redacted
);
CREATE TABLE IF NOT EXISTS webhook_dead_letter (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at     TEXT NOT NULL,
    reason          TEXT NOT NULL,
    delivery_id     TEXT,
    body_sha256     TEXT NOT NULL,
    body_bytes      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS refetch_request (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id      INTEGER REFERENCES webhook_receipt(id),
    kind            TEXT NOT NULL CHECK (kind IN ('calendar', 'reservation', 'full_reconcile')),
    property_id     TEXT,
    start_date      TEXT,
    end_date        TEXT,
    requested_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refetch_completion (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      INTEGER NOT NULL REFERENCES refetch_request(id),
    completed_at    TEXT NOT NULL,
    outcome         TEXT NOT NULL CHECK (outcome IN ('ok', 'failed')),
    detail          TEXT
);
CREATE TRIGGER IF NOT EXISTS webhook_receipt_no_update
    BEFORE UPDATE ON webhook_receipt
    BEGIN SELECT RAISE(ABORT, 'append-only: update on webhook_receipt refused'); END;
CREATE TRIGGER IF NOT EXISTS webhook_receipt_no_delete
    BEFORE DELETE ON webhook_receipt
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on webhook_receipt refused'); END;
CREATE TRIGGER IF NOT EXISTS webhook_dead_letter_no_update
    BEFORE UPDATE ON webhook_dead_letter
    BEGIN SELECT RAISE(ABORT, 'append-only: update on webhook_dead_letter refused'); END;
CREATE TRIGGER IF NOT EXISTS webhook_dead_letter_no_delete
    BEFORE DELETE ON webhook_dead_letter
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on webhook_dead_letter refused'); END;
CREATE TRIGGER IF NOT EXISTS refetch_request_no_update
    BEFORE UPDATE ON refetch_request
    BEGIN SELECT RAISE(ABORT, 'append-only: update on refetch_request refused'); END;
CREATE TRIGGER IF NOT EXISTS refetch_request_no_delete
    BEFORE DELETE ON refetch_request
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on refetch_request refused'); END;
CREATE TRIGGER IF NOT EXISTS refetch_completion_no_update
    BEFORE UPDATE ON refetch_completion
    BEGIN SELECT RAISE(ABORT, 'append-only: update on refetch_completion refused'); END;
CREATE TRIGGER IF NOT EXISTS refetch_completion_no_delete
    BEFORE DELETE ON refetch_completion
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on refetch_completion refused'); END;
