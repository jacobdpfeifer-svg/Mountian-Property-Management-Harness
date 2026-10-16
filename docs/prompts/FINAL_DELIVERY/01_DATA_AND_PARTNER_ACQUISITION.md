# Prompt 01 — data and partner acquisition

You are the data-acquisition lead. Build the data foundation required to price
three luxury Winter Park / Fraser homes safely and evaluate realized owner net.
Do not write pricing policy or rates. Do not place confidential data in Git.

## Objective

Produce a data-readiness dossier and ingestion contracts that remove every
external-data blocker for calibration, daily recommendations, operational
feasibility, and realized-profit measurement.

## Operator outreach request list

Ask the operator to obtain access or exports from the following parties. State
which exact fields are available before buying a product or signing a contract.

Request **24–36 months or two complete ski seasons** where available, then an
immutable daily delta feed. For the calendar, request point-in-time historical
snapshots rather than only its present state. Start a 365–540 day forward daily
snapshot and capture every change immediately; this is required to attribute an
eventual outcome to the price actually offered.

| Contact / system | Ask for | Minimum useful fields |
|---|---|---|
| Current PMS / Guesty account owner or integration contact | Read-only API and sandbox credentials; API limits; webhook catalog; rate-write/read-back semantics; reservation, listing, calendar, and financial export schemas | stable listing ID, property ID, stay dates, status/blocks, listed and booked nightly price, fees/taxes, channel, created/modified/cancelled timestamps, guest count, LOS, payout/commission fields, currency, timezone |
| PMS implementation/support contact | A documented canary procedure and rollback endpoint | idempotency key behavior, propagation lag, channel errors, audit trail, rate/min-stay/availability field separation |
| Channel partners (Airbnb, Vrbo, direct-booking stack) or PMS channel manager | Payout and fee settlement exports; cancellation/modification feed; displayed-price/fee behavior | reservation ID, channel, gross lodging, host fee, guest fees, taxes, payout, cancellation date/reason, modifications, booked/arrival/departure timestamps |
| Revenue-management / market-data vendors (evaluate AirDNA, Key Data, PriceLabs, Beyond, Wheelhouse, and a local STR data specialist) | A capacity-tiered Winter Park/Fraser comp dataset and pricing methodology | property attributes, capacity/bedrooms, location precision suitable for matching, nightly displayed price, price basis, availability, scrape/capture timestamp, length-of-stay assumptions, comp-set coverage, historical series |
| Local luxury STR property managers / comparable-home operators | Anonymous market and operational benchmarks, not guest PII | booking curves by season/lead bucket, LOS, cancellation, cleaning/turn costs, staffing constraints, minimum stays, maintenance outages, holiday rules, channel mix, fee structure |
| Cleaning/turn vendor, Turno, Breezeway, or equivalent | Historical and live turn/readiness feeds | reservation-linked turn ID, property, due/start/complete timestamps, cost, crew, exception, readiness state, cancellation and rework reason |
| Accounting/bookkeeping/payments owner | Owner-net source-of-truth exports and reconciliation policy | owner statement, lodging revenue, channel fees, management fee, cleaning/maintenance/consumables, refunds, taxes, payout date, owner allocation, chart-of-account mapping |
| Local legal/compliance advisor and insurance broker | Applicable permit, occupancy, local tax, insurance, and disclosure constraints | jurisdiction/property applicability, effective dates, document source, renewal/inspection dates, occupancy and safety restrictions |

## Required data contracts

Specify versioned, machine-readable contracts for these six datasets:

1. **Listing and inventory truth:** all rate, availability, block, and min-stay
   changes with source, effective time, and source-update time.
2. **Reservation lifecycle:** booking, modification, cancellation, and payout
   facts, joined by a stable reservation ID.
3. **Financial ledger:** actual owner net components. Do not infer owner net from
   ADR when a settlement/statement exists.
4. **Market/comp observations:** capacity-matched public prices and availability,
   explicitly tagged `nightly`, `stay_total`, `unknown`, or `includes_fees`.
5. **Operations readiness:** turn, incident, staffing, and property-unavailable
   facts needed to keep a price recommendation serviceable.
6. **External events:** resort, road, weather, flight, calendar, and regulatory
   observations with observed timestamp, source URL/identifier, freshness target,
   and failure behavior.
7. **Price decisions:** an append-only record of proposed, approved, rejected,
   applied, verified, and rolled-back changes, including prior observed value,
   policy/calibration/input hashes, approver, and reason.

For each contract document: primary key; property/listing mapping; field type;
units/currency/timezone; nullability; source-of-truth; latency; historical depth;
privacy classification; retention; reconciliation query; freshness/coverage
threshold; and fail-closed behavior.

## Quality gates

Do not certify a feed until all of the following are demonstrated:

- Stable identifiers map exactly to the three declared portfolio properties; any
  extra PMS listing is quarantined from pricing.
- Amounts reconcile from PMS/channel facts through the owner statement within a
  documented tolerance; unexplained differences remain visible.
- At least one full booking lifecycle, including a modification or cancellation
  if available, can be traced without manual guesswork.
- Every comp quote has a capture timestamp, property attributes, availability
  status, and price-basis tag. `unknown` price basis cannot calibrate a price
  model.
- Dataset coverage is reported by property, season, lead bucket, channel, and
  date—not as a single portfolio percentage.
- Reservation count and money totals reconcile at or above 99% to PMS and owner
  statements; every remainder has an explicit exception reason.
- No guest PII or secrets are committed. Aggregates only may enter
  `data/exports/`.

## Required deliverables

1. `docs/reports/final_delivery/DATA_READINESS.md`
2. A field-level data dictionary and source mapping.
3. A vendor comparison table that distinguishes data ownership, coverage,
   historical availability, price basis, export/API access, and commercial terms.
4. Fixtures and contract tests for every approved feed.
5. A gap register containing only concrete acquisition or implementation actions.

## Do not accept

- Screenshots, dashboards, unexportable aggregates, or verbal assurances as a
  production source of truth.
- Market-wide ADR as a proxy for luxury 16–18 guest homes.
- A feed that cannot identify whether a displayed rate includes mandatory fees.

## Technical integration note

Guesty webhook payloads are event notifications, not automatically the
authoritative current record. Design the integration as `validate signature →
persist immutable event → deduplicate → re-fetch Guesty truth → reconcile`.
The integration must tolerate duplicate/out-of-order webhooks and must subscribe
to the appropriate reservation and calendar events because calendar events do
not cover every reservation/rule-driven block. Require HTTPS endpoint, signing
secret, replay behavior, and sandbox/canary access from Guesty before building
inbound automation.
