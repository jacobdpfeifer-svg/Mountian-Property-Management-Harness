# Data readiness dossier

Assessment date: 2026-10-15 (after the data-spine pass).
Readiness decision: **BLOCKED** on real data. The contracts, storage, and
reconciliation logic that real data needs now exist and are tested on synthetic
fixtures.

## What the repository now provides

- Versioned contracts (`src/data_spine/contracts.py`, schema version `1.0` each)
  for price decisions, reservations, calendar observations, financial ledger
  lines, owner statements, market observations, ops tasks, and listing
  constraints. Each declares every accepted field; anything else (guest names,
  emails, raw payloads) is dropped.
- Append-only tables with lineage on every row: entity key, version, superseded
  row, correction reason, source system and record id, content hash, schema
  version, source-updated / observed / ingested times, and batch.
- Quarantine with reason codes for ambiguous identity, money, price basis, time,
  inconsistency, or out-of-order updates.
- Owner net `owner_net.v1`, statement reconciliation, and a full trace from
  decision to owner statement.

## Contract and evidence status

| Required dataset | Contract | Real evidence | State | Exact input needed |
|---|---|---|---|---|
| Listing and calendar truth | `calendar_observation` | aggregate local rate card only | BLOCKED | Guesty read-only calendar export/API history with observed timestamps (request 1). |
| Reservation lifecycle | `reservation` | none approved | BLOCKED | De-identified bookings, modifications, cancellations keyed by stable reservation id, with stay-total lodging and guest fees separated (request 1). |
| Financial ledger | `financial_ledger` | none | BLOCKED | Channel payout/settlement lines and management/cleaning charges per reservation (request 3). |
| Owner statements | `owner_statement` | none | BLOCKED | Monthly owner statements for the three homes, net figure per statement (request 3). |
| Market/comp observations | `market_observation` (price basis required) | local scrapes without certified basis | BLOCKED | Capacity-matched sample with each quote tagged nightly vs stay total and fees included or not (request 5). |
| Operations readiness | `ops_task`, `listing_constraint` | demo samples | BLOCKED | Turno/Breezeway/Guesty Tasks export or read credential (request 4). |
| Price decisions | `price_decision` | contract + review queue built; no production rows | NOT_MEASURED | Produced by shadow operation once it starts. |

## Owner net: actual inputs vs assumptions

| Component | Source when actual | Today |
|---|---|---|
| Gross lodging, guest/cleaning fee income | reservation + settlement lines | not available |
| Channel fee (Airbnb/VRBO/Booking), payment processing (direct) | settlement lines | not available |
| Management fee | owner statement / management agreement | `management_fee_pct: null` in `config/portfolio/mont_luxe.yaml` (operator-confirm) |
| Cleaning/turn cost, consumables, maintenance | statement or ops provider | not available |
| Refunds, damage recovery | settlement lines | not available |
| Taxes | recorded for reconciliation, excluded from owner net | — |

Until actual lines exist, any owner-net figure is labelled `partially_assumed`
with each assumed component named, or `incomplete`. Simulated owner net (V2)
remains simulated.

## Certification gate (unchanged)

Exact mapping to the three homes; at least one real booking traced end to end;
price-basis tags on every comp observation; coverage by property/season/lead/
channel; ≥99% reconciliation of reservation counts and money totals to PMS and
owner statements, with every exception named.
