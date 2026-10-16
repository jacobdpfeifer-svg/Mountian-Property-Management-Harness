# Ingestion mapping — what each source fills, and how

Code: `src/data_spine/adapters.py`, `src/data_spine/backfill.py`. Mapping files: `config/data_mapping/`.
Commands: `wp-price spine-backfill-guesty`, `wp-price spine-import`. Every record passes a versioned
contract (`src/data_spine/contracts.py`). Anything ambiguous is **quarantined with a reason, never guessed**,
and columns that are not mapped (guest names, emails, notes) are dropped before storage.

## Sources and status

| # | Source | Fills (contract) | How | Status |
|---|---|---|---|---|
| 1 | Guesty Open API — reservations (read-only) | `reservation`, `financial_ledger` (pending) | `spine-backfill-guesty --since 2021-01-01` | **Ready to run** with the current read credentials |
| 2 | Guesty Open API — calendar (read-only) | `calendar_observation` | same command | **Ready** |
| 3 | Accounting export (Guesty Accounting, QuickBooks, …) | `financial_ledger` (settled), incl. management fee, cleaning cost, refunds | `spine-import --mapping accounting_ledger.yaml` | Template ready; **needs the real export** |
| 4 | Owner statements | `owner_statement` (reconciliation target) | `spine-import --mapping owner_statement.yaml` | Template ready; **needs statements** |
| 5 | Operations / turnover system | `ops_task` (turn costs, failures) | `spine-import --mapping ops_tasks.yaml` | Template ready; **needs export** |
| 6 | Owner blocks / maintenance | `listing_constraint` | mapping file (same pattern) | Needs a list from the operator |
| 7 | Capacity-matched comps | `comps.bedrooms/sleeps` + `comp_set_members` | `discover-comps` + tier filter (`src/comps`) | Exists; scrape success is the problem (below) |

## Guesty reservation → spine

| Spine field | Guesty field | Rule |
|---|---|---|
| reservation_key | `_id` | `guesty:<_id>` |
| property_id | `listingId` | through the locked listing map; an unknown listing is skipped |
| channel | `source` | airbnb/airbnb2 → airbnb; homeaway/vrbo → vrbo; booking.com → booking_com; manual/direct/website → direct; owner → owner; **else other** |
| status | `status` | confirmed/reserved/checked_in/checked_out → confirmed; canceled → cancelled; inquiry/declined/expired → **not a stay, skipped** |
| check_in / check_out / nights | `checkIn` / `checkOut` / `nightsCount` | nights must equal the date span, else quarantined |
| booked_at | `confirmedAt`, else `createdAt` | must carry a timezone |
| source_updated_at | `lastUpdatedAt`, else `createdAt` | versioning: an older update than the stored one is quarantined |
| gross_lodging | `money.fareAccommodation` | **stay total before guest fees and taxes** (`stay_total_ex_fees`) |
| guest_fees | `money.fareCleaning` | missing → quarantined |

Ledger lines from Guesty are `basis=actual, settlement_state=pending`: gross_lodging, cleaning_fee_income,
and (OTA channels only) channel_fee from Guesty's itemized host service fee, never inferred from payout.
Cancelled stays create no lodging lines; refunds and cancellation fees come from accounting (source 3).

## Accounting export → ledger

The template (`accounting_ledger.template.yaml`) maps category labels to entry types. **Value maps are
exhaustive.** A label not in the map (for example "Mystery Line") is quarantined as `BAD_ENUM` until
someone adds it. Amounts are taken as absolute; direction comes from the entry type (refund is a
debit, damage recovery a credit). Settlement status Paid/Settled → settled, Void → reversed.
A settled line without a settled date is quarantined.

**One source of money per stay.** Once any accounting line exists for a reservation, every Guesty
(booking-time) line for it is ignored, and the accounting lines, pending and settled, are the stay's
money. So the accounting export must carry the stay's revenue lines (accommodation, fees, channel
commission) as well as its costs. Mixing the two sources by category double-counted lodging,
under-counted partial settlements and double-counted bundled cleaning (2026-10-16 audit, V6). A Guesty
cancellation re-issues the booking lines as `reversed`.

Owner net per stay (`owner_net.v1`) is complete only when gross lodging, management fee and cleaning cost
are all present as actual lines (plus channel fee for OTA stays). Until the accounting export arrives,
every stay's owner net is `incomplete`, and **no realized-profit claim is possible**.

## Owner statements

Statements are the reconciliation target, not a source of stay economics. `reconcile_statement`
compares the sum of a period's settled owner net with the statement's reported net and lists the gap.

## Known data problems to fix first

1. **Scrape success.** 67% of comp scrape rows failed (2026-09-20 .. 10-16), with four 3–4-day blackouts.
   Under the repaired anchor rule (42-day cap, 3 comps) only 3% of Northwoods nights get a market
   anchor. Fixing the scraper is worth more than any pricing change
   (docs/reports/anchor_rule_study/DECISION.md).
2. **Short local history.** The operator database holds reservations only from 2026-05. The multi-year
   pull (source 1, `--since 2021-01-01`) is the first step.
3. **Stale recommendations.** The latest engine run in the operator database is from 2026-09-21. Shadow
   mode refuses to queue stale prices, so `recommend` must run daily before `shadow-day`.
