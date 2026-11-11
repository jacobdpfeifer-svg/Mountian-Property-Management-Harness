# Forward shadow log for operations (Stage 4.4): specification, not built

**Why not built in this pass:** the operator has no task feed yet (the replay found zero task
outcomes), so a logger would record predictions with nothing to score them against. Build it
the day a task source (Guesty Tasks, Breezeway, or a CSV export) is confirmed. Estimated
effort: about 1 day for the module and tests, plus a daily launchd line beside
`com.wpprice.pacing`.

## Shape

A sibling of `src/eval/shadow.py` at `src/ops/forward_shadow.py`. It uses the same rules:
- It never sits on a database that has written live rates (reuse `GuestyWriteForbidden`).
- It opens read-only except for its own table.
- It runs once a day after the Guesty sync.

```sql
CREATE TABLE IF NOT EXISTS ops_shadow_daily (
    as_of               TEXT NOT NULL,     -- decision date the prediction was made
    turn_id             TEXT NOT NULL,     -- property|departing|arriving (as of as_of)
    property_id         TEXT NOT NULL,
    service_date        TEXT NOT NULL,
    lead_days           INTEGER NOT NULL,  -- service_date - as_of
    gap_nights          INTEGER,           -- NULL = no arrival yet
    slack_minutes       REAL,
    weather_buffer_min  REAL,
    p_ready             REAL NOT NULL,     -- Beta-shrunk prediction
    p_ready_basis       TEXT NOT NULL,     -- prior | observed, with n
    p_bucket_max_slack  REAL,
    turn_cost           REAL NOT NULL,
    turn_cost_basis     TEXT NOT NULL,     -- estimate | observed
    zone_utilization    REAL,              -- capacity view for the service date
    profile_version     TEXT NOT NULL,
    readiness_state     TEXT NOT NULL,     -- state_for_night(service_date) at as_of
    -- filled later by score_ops_shadow(); NULL until the outcome is imported
    outcome_task_id     TEXT,
    late_ready_minutes  REAL,              -- <= 0 is on time
    actual_cost         REAL,
    outcome_joined_by   TEXT,              -- turn_id | service_date | none
    PRIMARY KEY (as_of, turn_id)
);
```

Record every turn whose service date is 0 to 14 days ahead, at each decision date. One turn is
therefore predicted at many lead times, which is how calibration by lead time gets measured.

## Scoring (`score_ops_shadow`, run weekly and in the owner/ops report)

Join outcomes from `turnover_outcomes` by `turn_id`, else by (property, service date). The
join method is stored. A turn whose reservation was cancelled after `as_of` is scored as
`no_turn`, not as on-time.

| Metric | Definition | Pass bar to consider `ops_aware_stay` |
|---|---|---|
| Brier score of P(ready) | mean (p − on_time)² by lead bucket (0–1, 2–3, 4–7, 8–14 days) | below the prior-only Brier on the same turns |
| Calibration | reliability curve: predicted P in deciles vs observed on-time rate, with counts | every decile with n ≥ 10 within ±0.10 |
| Late-turn recall | share of late turns that were flagged (P < `stay.min_p_ready` or utilization ≥ critical) 1+ day ahead | ≥ 0.5 |
| Cost error | median and MAE of turn_cost − actual_cost, by basis | MAE under 15% of the median actual cost |
| Coverage | share of service dates with any outcome joined | ≥ 0.8 before any metric is trusted |

Report n beside every number. At 3 homes there are about 40 to 70 turns a ski season,
so expect a season before calibration means anything. Say that in the report, not in a
footnote.
