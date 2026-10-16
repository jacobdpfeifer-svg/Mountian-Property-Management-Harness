# Prompt 07 — operator outreach templates

These are copy/paste requests. Send the first four in parallel. Do not send raw
guest PII, payment-card details, bank details, or full guest communications to
the repository team.

## 1. PMS / Guesty account administrator

> We are building an internal, safety-first owner-net pricing and operations
> system for the three Mont Luxe homes. We need a read-only integration and a
> historical export first; this request does not authorize price writes.
>
> Please connect us with the Guesty Open API/technical owner and provide: API
> entitlement and rate limits; sandbox or isolated test-listing availability;
> data dictionary; read-only OAuth/API setup; reservation, listing, calendar,
> task, payment/payout, and webhook capabilities; audit/export options; calendar
> block/restriction semantics; and rate write/read-back/rollback behavior.
>
> We need a deidentified historical and ongoing export for the declared homes:
> stable listing/reservation IDs; nightly rates and availability/restrictions by
> observed time; booking/modification/cancellation timestamps; stay dates;
> channel; rate plan; fee/tax/payout fields; and property task/block facts. Please
> state historical coverage, export/API terms, update cadence, timezone, and a
> technical reconciliation contact. We will use stable hashed IDs and will not
> require guest contact, identity, card, or message content.

## 2. Owner, property manager, and revenue manager

> We are validating a pricing system against current practice, not replacing
> operator judgment. Please provide the authoritative current rate calendar,
> historical price/min-stay/availability changes and override reasons, owner-use
> blackout rules, event/holiday rules, price floors/ceilings, channel strategy,
> and who can approve, reject, roll back, or emergency-stop a pricing change.
>
> Please also provide the management agreement and actual fee treatment by home
> and channel: management percentage, channel/processing fees, cleaning and
> linen treatment, guest fees, refunds/concessions, owner allocations, and any
> special costs. We need the current-practice rationale so the test compares the
> system to the real operating baseline rather than a generic flat rate.

## 3. Accounting / bookkeeping / finance owner

> We need to calculate realized owner net from settled facts. Please provide a
> deidentified reservation-level or statement-line export and reconciliation
> guide for the portfolio: accommodation revenue, retained guest fees, channel
> and payment fees, management fee, cleaning/turn/maintenance costs, refunds,
> chargebacks, taxes/remittances, owner allocation, payout date, and owner net.
>
> Please identify the canonical owner statement, chart-of-account mapping, known
> timing differences, and the person who can resolve exceptions. The request is
> for financial aggregates and hashed booking IDs only; no bank account, guest
> identity, or payment-card data is needed.

## 4. Operations / housekeeping / maintenance lead

> We need to ensure that a price recommendation never creates a stay the homes
> cannot service. Please provide completed and planned turn/readiness data by
> property: task ID, reservation/stay reference if available, due/start/complete
> times, crew/vendor, cost, inspection result, rework, maintenance incident,
> block/out-of-service reason, capacity constraints, service cutoffs, snow or
> access constraints, and escalation contacts.
>
> Please include the operational rules that are non-negotiable for accepting a
> booking and identify which system is the source of truth (Turno, Breezeway,
> Guesty Tasks, or another tool).

## 5. Market-data vendor sales / data specialist

> We are evaluating licensed Winter Park/Fraser market data for large luxury
> homes, not a generic market-ADR dashboard. Before purchase, please provide a
> data dictionary and a sample export/API response for capacity-matched homes.
>
> We require date-specific historical and forward observations with capture time,
> bedrooms/sleeps/amenities/location tier, nightly versus stay-total/all-in price
> basis, mandatory-fee treatment, availability/booked/blocked methodology,
> comp-set control, season/event/pacing fields, refresh cadence, historical depth,
> API/export limits, model-training/internal-retention rights, SLA, and exit
> export terms. Please distinguish observed facts from inferred availability or
> booking status.

## 6. Peer luxury property managers / revenue-management adviser

> We are seeking an independent review and, where permitted, anonymized control
> data from comparable Colorado mountain luxury homes. We need a consistent
> deidentified export of nightly rate/availability history, reservation lifecycle,
> fees/owner net, cancellations, operations costs, and property attributes for
> two or more ski seasons. We will operate under an NDA/DPA, use no guest PII,
> publish only aggregate findings, and will not identify their listings.
>
> We also want a review of our comp construction, guardrails, holiday/last-minute
> rules, approval/rollback policy, and experiment design. Please state whether
> you can supply data, advisory review, or both.

## 7. Local compliance, tax, and insurance advisers

> Please confirm the current requirements that apply to each identified property:
> STR registration/business license, renewal and inspection requirements,
> responsible-agent requirements, occupancy/parking/noise/safety restrictions,
> lodging-tax and mandatory-fee treatment, insurance exclusions, data-retention
> obligations, and authority/contract requirements for a manager or software
> system to alter published rates. Please cite the controlling jurisdiction and
> effective date, and flag any property-specific exception.

## What to return to the delivery team

For every response, send the data dictionary, sample, historical coverage,
timezone/currency, API/export terms, terms for internal model use and retention,
named reconciliation contact, and written confirmation of whether access is
read-only or write-capable. A screenshot or marketing dashboard is not a usable
integration response.
