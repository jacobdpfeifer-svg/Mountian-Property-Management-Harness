# Data readiness dossier — initial assessment

Assessment date: 2026-10-15  
Readiness decision: **BLOCKED**.

The repository has a useful confidential aggregate rate-card export for V2
calibration. It does not establish authoritative inventory history, reservation
lifecycle, settlement-level owner net, market price basis, operational
readiness, external events, or price-decision lineage. No external access or
data purchase is implied by this report.

## Contract and evidence status

| Required dataset | Current evidence | State | Concrete acquisition / implementation action |
|---|---|---|---|
| Listing and inventory truth | Aggregate local rate card; no point-in-time calendar history | BLOCKED | Obtain Guesty/PMS read-only export/API and daily immutable snapshots, with rate/min-stay/block source and observed timestamps. |
| Reservation lifecycle | No approved historical reservation feed | BLOCKED | Obtain deidentified booking, modification, cancellation, and payout export keyed by stable reservation ID. |
| Financial ledger | No owner-statement or settlement-line feed | BLOCKED | Obtain channel/PMS settlement and owner statement exports, chart-of-account mapping, and exception contact. |
| Market/comp observations | Local scrape inputs exist; no approved coverage/price-basis certification | BLOCKED | Obtain capacity-matched vendor sample and tag every quote as `nightly`, `stay_total`, `includes_fees`, or `unknown`. |
| Operations readiness | Demo-like local samples only | BLOCKED | Obtain Turno/Breezeway/Guesty Tasks source and map turn, incident, capacity, and block facts. |
| External events | Code collectors exist; no freshness/coverage certification | BLOCKED | Document source, observed time, legal use, freshness target, and fail-closed behavior per event feed. |
| Price decisions | No append-only production decision ledger | BLOCKED | Implement a versioned proposed/approved/rejected/applied/verified/rolled-back receipt contract. |

## Acceptance requirements for an approved feed

Every contract must specify primary key; three-property mapping; fields and
units; timezone/currency; nullability; source of truth; historical depth;
latency; privacy and retention classification; source/update/observed times;
reconciliation query; coverage/freshness threshold; and fail-closed behavior.

Certification requires exact mapping to the three declared homes, at least one
traceable booking lifecycle, price-basis tags for comp observations, coverage
reported by property/season/lead/channel/date, and >=99% reconciliation of
reservation counts and money totals to PMS and owner statements. All remaining
differences must have a named exception reason.

## Operator requests ready to send

Use `docs/prompts/FINAL_DELIVERY/07_OPERATOR_OUTREACH_TEMPLATES.md` requests
1–4 first: Guesty/PMS administrator, owner/property/revenue manager,
accounting, and operations lead. They request only deidentified fields and
read-only access; they do not authorize a pricing write.
