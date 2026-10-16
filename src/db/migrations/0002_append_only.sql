-- 0002_append_only: the data spine is never updated or deleted in place.
-- A correction is a new version row (see 0001). These triggers make that a
-- database property rather than a convention.

CREATE TRIGGER IF NOT EXISTS spine_source_batch_no_update
    BEFORE UPDATE ON spine_source_batch
    BEGIN SELECT RAISE(ABORT, 'append-only: update on spine_source_batch refused'); END;
CREATE TRIGGER IF NOT EXISTS spine_source_batch_no_delete
    BEFORE DELETE ON spine_source_batch
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on spine_source_batch refused'); END;

CREATE TRIGGER IF NOT EXISTS spine_quarantine_no_update
    BEFORE UPDATE ON spine_quarantine
    BEGIN SELECT RAISE(ABORT, 'append-only: update on spine_quarantine refused'); END;
CREATE TRIGGER IF NOT EXISTS spine_quarantine_no_delete
    BEFORE DELETE ON spine_quarantine
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on spine_quarantine refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_price_decision_no_update
    BEFORE UPDATE ON fact_price_decision
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_price_decision refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_price_decision_no_delete
    BEFORE DELETE ON fact_price_decision
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_price_decision refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_reservation_version_no_update
    BEFORE UPDATE ON fact_reservation_version
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_reservation_version refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_reservation_version_no_delete
    BEFORE DELETE ON fact_reservation_version
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_reservation_version refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_reservation_night_no_update
    BEFORE UPDATE ON fact_reservation_night
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_reservation_night refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_reservation_night_no_delete
    BEFORE DELETE ON fact_reservation_night
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_reservation_night refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_calendar_observation_no_update
    BEFORE UPDATE ON fact_calendar_observation
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_calendar_observation refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_calendar_observation_no_delete
    BEFORE DELETE ON fact_calendar_observation
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_calendar_observation refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_financial_ledger_no_update
    BEFORE UPDATE ON fact_financial_ledger
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_financial_ledger refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_financial_ledger_no_delete
    BEFORE DELETE ON fact_financial_ledger
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_financial_ledger refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_owner_statement_no_update
    BEFORE UPDATE ON fact_owner_statement
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_owner_statement refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_owner_statement_no_delete
    BEFORE DELETE ON fact_owner_statement
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_owner_statement refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_market_observation_no_update
    BEFORE UPDATE ON fact_market_observation
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_market_observation refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_market_observation_no_delete
    BEFORE DELETE ON fact_market_observation
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_market_observation refused'); END;

CREATE TRIGGER IF NOT EXISTS fact_ops_task_no_update
    BEFORE UPDATE ON fact_ops_task
    BEGIN SELECT RAISE(ABORT, 'append-only: update on fact_ops_task refused'); END;
CREATE TRIGGER IF NOT EXISTS fact_ops_task_no_delete
    BEFORE DELETE ON fact_ops_task
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on fact_ops_task refused'); END;

CREATE TRIGGER IF NOT EXISTS dim_listing_constraint_no_update
    BEFORE UPDATE ON dim_listing_constraint
    BEGIN SELECT RAISE(ABORT, 'append-only: update on dim_listing_constraint refused'); END;
CREATE TRIGGER IF NOT EXISTS dim_listing_constraint_no_delete
    BEFORE DELETE ON dim_listing_constraint
    BEGIN SELECT RAISE(ABORT, 'append-only: delete on dim_listing_constraint refused'); END;
