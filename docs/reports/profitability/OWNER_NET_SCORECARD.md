# Owner-net scorecard

Date: 2026-10-20. Result for every home: **INCOMPLETE**. This is not settled owner net and it is not realized profit.

## Formula

For each reservation, from current non-reversed ledger lines (`owner_net.v1` in [src/data_spine/owner_net.py](../../../src/data_spine/owner_net.py)):

settled lodging (`gross_lodging`)
+ retained guest fees (`guest_fee_income` only)
+ cleaning-fee income, kept as its own line until an operator says it is retained
− channel and payment fees
− management fee
− cleaning and turn cost
− consumables
− stay maintenance
− refunds, concessions, and chargebacks
+ damage recovery when a line exists
= owner net

Taxes and owner payouts stay out of the total. System operating cost is a separate hurdle. Mortgage, depreciation, property tax, and broad ownership costs are named and excluded.

Each display field is `actual`, `assumed`, `missing`, or `not_applicable`. An absent optional cost is `not_applicable`, not an actual zero. A direct or owner stay with no channel or payment line has channel-and-payment fees `not_applicable`. An owner-block night has lodging `not_applicable`.

`property_month` prorates a stay evenly across its nights and sums the nights inside the month. The label is `settled` only when every included stay is actual, nothing required is missing, nothing is pending, and statement reconciliation is at least 99% by count and by value. Otherwise the label is `INCOMPLETE` or `partially_assumed`. `render_owner_month` refuses to print "realized profit".

## Evidence

Command, against the gitignored read-only spine, for 2026-01-01 through 2026-10-20:

| Property | Stays in window | Statement reconciliation | Label |
|---|---|---|---|
| cloud_9 | 7 | none (no statement) | INCOMPLETE |
| overlook_ridge | 16 | none | INCOMPLETE |
| summit_haus | 27 | none | INCOMPLETE |

Guesty lines in that database: 159 pending, 0 settled, 0 owner statements. Pending booking money is not settled lodging.

## Hurdle

`required incremental owner net per available night = annual system operating cost / annual sellable nights`.

`config/local/system_cost.yaml` does not exist. The example [config/local/system_cost.example.yaml](../../../config/local/system_cost.example.yaml) has nulls and no invented dollars. `wp-price owner-net-month` now loads that gitignored file by default (explicit CLI values can override its portfolio totals). Hurdle status: **missing**. Per-available-night: not calculated. A per-property figure is also missing. It will be reported only when cost shares, each home's sellable nights, and a named allocation method are all supplied, so one home's nights are not used to hide another's cost.

## Tests

- `tests/data_spine/test_owner_net_scorecard.py`: direct channel fee `not_applicable`; owner-block lodging `not_applicable`; unlinked money quarantined; a duplicated ledger line fails reconciliation; a statement that does not match stays `INCOMPLETE` below 99% by value; hurdle is missing without inputs and, with explicit inputs of 10000 / 500 nights, is 20.00 per night, or 50.00 and 12.50 when a 50/50 cost share meets 100 and 400 nights.
- Existing spine tests still cover corrections, cancellations, partial refunds, and statement mismatch: `tests/data_spine/test_data_spine.py`.
- Quality gates 2026-10-20: 1113 passed, coverage 80.83%.

The legacy HTML receipt in [src/receipt/owner_monthly.py](../../../src/receipt/owner_monthly.py) still reads the older tables. It is not this scorecard and it is not settled owner net.

## Assumptions

No management-fee percent, no system cost, and no sellable-night count were assumed.

## Exceptions

No owner statement to reconcile. Every live money line is pending. Two reservations never entered the spine (`INCONSISTENT:nights`).

## External dependencies

Monthly owner statements, settlement lines, written fee treatment, and `config/local/system_cost.yaml` filled by the operator.

## Next action

Import statements with `config/data_mapping/owner_statement.template.yaml` and settlement lines with `accounting_ledger.template.yaml`, then run:

```bash
wp-price owner-net-month --db data/profitability_readonly.db \
  --property summit_haus --start 2026-01-01 --end 2026-01-31
```

Repeat for `overlook_ridge` and `cloud_9`. A non-zero exit means the month is not settled.
