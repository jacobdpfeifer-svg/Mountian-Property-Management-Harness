-- 0003_audit_events: security/scope/write-control events, redacted before insert.
CREATE TABLE IF NOT EXISTS audit_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at  TEXT NOT NULL,
    environment  TEXT NOT NULL,
    event_type   TEXT NOT NULL,     -- scope_quarantine | write_refused | kill_switch | credential | webhook | canary | review
    boundary     TEXT NOT NULL,     -- sync | webhook | recommendation | audit | push | canary | review
    severity     TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    subject      TEXT,
    detail_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type, occurred_at);
CREATE TRIGGER IF NOT EXISTS audit_events_no_update
    BEFORE UPDATE ON audit_events
    BEGIN SELECT RAISE(ABORT, 'append-only: update on audit_events refused'); END;
CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
    BEFORE DELETE ON audit_events
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on audit_events refused'); END;
