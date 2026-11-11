# Economic baseline

Date: 2026-10-20. Decision: **BLOCKED_ON_EXTERNAL_DATA**. Guesty writes: **0**.

Settled owner net is not measured for Summit Haus, Overlook Ridge, or Cloud 9. A read-only Guesty pull loaded booking-time reservations and a short calendar into a gitignored database. Channel settlement lines and owner statements were not in that pull, and no accounting export was supplied.

## Evidence

- Gitignored spine: `data/profitability_readonly.db` (not tracked).
- Scope: `PortfolioScope` / `EXPECTED_PROPERTY_IDS` in [src/security/scope.py](../../../src/security/scope.py). All three homes resolved. One additional Guesty listing was outside that scope and was not imported.
- Contracts: [src/data_spine/contracts.py](../../../src/data_spine/contracts.py). Money with neither a reservation key nor a statement key quarantines as `UNLINKED_MONEY`.
- Templates (tracked, unfilled): `config/data_mapping/*.template.yaml`. Filled copies belong in gitignored `imports/private/`.

## Commands

```bash
.venv/bin/python - <<'PY'
# Read-only census, then backfill_guesty into data/profitability_readonly.db.
# GuestyClient via ReadOnlyGuesty. calendar_days=14, check_in_from=2020-01-01.
# No set_rate, no reservation create, no availability write.
PY
```

The census and backfill ran in this session through `ReadOnlyGuesty` and `backfill_guesty`. The wrapper has no write method.

## What was ingested

| Contract | Accepted | Quarantined | Notes |
|---|---|---|---|
| reservation | 78 | 2 | 2 rows `INCONSISTENT:nights` (stay length did not match the dates). 49 non-stays skipped (inquiry, declined, expired). |
| financial_ledger | 211 | 0 | 159 current lines are `pending`; 52 cancelled-booking lines are `reversed`. Settled lines: 0. 5 lines skipped because their reservation was quarantined. |
| calendar_observation | 45 | 0 | 14 forward days plus the as-of day, three homes. Nightly rate before fees, observed at ingest time. This is not a historical rate archive. |
| owner_statement | 0 | — | No export. |
| market_observation | 0 | — | No capacity-matched file with an explicit price basis. |
| ops_task | 0 | — | No Turno, Breezeway, or Guesty Tasks export. |

Mapped current reservation counts (internal property ids only): Overlook Ridge 27, Summit Haus 37, Cloud 9 14, of which 55 are confirmed and 23 cancelled.

## Trace

One confirmed Overlook Ridge stay was traced with `trace_reservation`: one reservation version, three nights, three pending ledger lines, **zero** owner statements. `owner_net` status: `incomplete`. The chain stops before settlement. That is not a realized trace.

## Field classification

| Input | Class |
|---|---|
| Guesty listing mapping for the three homes | actual (locked local map; ids are not in this report) |
| Extra Guesty listing | out of scope; not imported |
| Management fee by property and channel | missing (`management_fee_pct: null` in `config/portfolio/mont_luxe.yaml`) |
| Channel and payment fee treatment | missing as an operator term. Guesty pending channel-fee lines exist for channel stays; they are not settled. |
| Retained versus pass-through guest fees | missing |
| Cleaning, turn, maintenance cost treatment | missing |
| Summit Haus jurisdiction | missing. Not inferred from a mailing city. |
| Overlook Ridge jurisdiction | missing. Same reason. |
| Cloud 9 jurisdiction | missing as an operator confirmation. Config says Fraser and the Fraser rule pack exists; the operator has not confirmed it. |

## Jurisdiction sources checked 2026-10-20

These describe the rules of a place. They do not assign a home.

- Town of Fraser, https://www.frasercolorado.com/303/Short-Term-Rental. Ordinance 449 effective 2017-12-17; Ordinance 488 effective 2022-09-24; Ordinance 516 passed 2024-12-04, fire inspection required for new registrations and renewals after 2025-02-28. The town tells owners to use its map because Fraser and unincorporated Grand County are different regimes. Uncertainty: later amendments after Ordinance 516 were not re-read from the municipal code in this pass.
- Town of Winter Park, https://wpgov.com/doing-business/rent-your-home/. Nightly or sub-31-day rentals inside town limits need a business license, sales tax, and STR registration. The fetched page does not restate an ordinance effective date. The repo pack `config/compliance/winter_park.yaml` still cites `effective_from: 2025-08-01` from the 2026-10-06 audit. That date was not re-proven from the page text today.
- Unincorporated Grand County, https://www.co.grand.co.us/943/Short-Term-Rentals. Annual permit, fee $100 per advertised occupant, maximum occupancy 16. The page says the permit is not for Winter Park, Fraser, Granby, or Grand Lake. The zoning amendment date 2026-07-28 remains the date in `config/compliance/grand_county_unincorporated.yaml`; this page fetch did not restate it.

## Tests

`scripts/quality_gates.py` on 2026-10-20: **1113 passed**, 3 deselected, coverage 80.83%, vulture clean, mypy clean, `scan_repo.py` 0 problems. Targeted file: `tests/data_spine/test_owner_net_scorecard.py` (unlinked money, direct-channel fee, owner block, duplicate line, hurdle).

## Assumptions

None were substituted for settlement, management-fee percent, fee treatment, or jurisdiction.

## Exceptions

- 2 reservations quarantined, `INCONSISTENT:nights`.
- 5 ledger lines held back with those reservations.
- 1 Guesty listing outside the three-home scope, not imported.
- Every Guesty money line is pending. Reconciliation to an owner statement cannot be computed.

## External dependencies

Settlement export, monthly owner statements, ops costs, a certified comp file, written fee terms, and a written jurisdiction for each home. Copy the templates into `imports/private/` and use `wp-price spine-import`. Requests are in `EXTERNAL_BLOCKERS_AND_REQUESTS.md`.

## Next action

Send the accounting and owner-statement request and import the files with the templates. Do not treat this Guesty pull as settled owner net.
