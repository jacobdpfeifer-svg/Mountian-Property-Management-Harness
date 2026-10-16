# Canary runbook (workstream 8) — INACTIVE

The canary is the first time the engine's price reaches a live listing. It stays inactive by construction:
no code builds a `CanaryAuthorization` (tests/security/test_canary.py). Activating it is a separate,
reviewed change.

## Before anything: every gate must read PASS

    wp-price canary-readiness --register <frozen V3 register> --plan <frozen field plan>

Gates: evaluation PASS · ≥ 28 shadow days with a ≥ 14-day unbroken streak · ≥ 90% healthy days ·
≥ 80% of shadow nights reviewed · zero rate writes · market anchor on ≥ 50% of nights · frozen
field plan naming this experiment · settled ledger lines and owner statements for the canary home ·
a valid operator sign-off.

## The operator sign-off (written by a person, never by code)

`~/.wp-price/control/canary_signoff.json`:

    {"authorization_id": "CAN-2027-01-A", "experiment_id": "EXP-PACE-V3-001", "plan_id": "FT-PACE-V3-2027W",
     "property_id": "cloud_9", "dates": ["2027-01-11", "2027-01-12", "2027-01-13"],
     "approver": "<name>", "rollback_owner": "<name>", "max_abs_move": 150, "max_pct_move": 0.08,
     "max_writes": 3, "floor_price": 900, "expires_at": "2027-01-10T23:00:00-07:00",
     "kill_switch_tested_at": "2027-01-09T09:00:00-07:00"}

Rules the gate enforces: one home; every date is a treatment night of the frozen plan; moves of at most 10%;
at most 14 writes and never fewer than the number of dates; named approver and rollback owner; kill switch
tested within 7 days; not expired. A write additionally needs the separate write permit and
`WP_PRICE_ENV=production` (src/security/kill_switch.py).

## During and after

- `wp-price field-stop-check --plan …` weekly; any fired rule stops treatment pricing.
- Engage the kill switch at any doubt: `python -m src.security.kill_switch engage`.
- Each canary write is read back; a mismatch aborts and rolls back (src/pms/canary.py).
