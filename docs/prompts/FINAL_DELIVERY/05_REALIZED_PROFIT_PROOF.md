# Prompt 05 — realized owner-net proof

You are the independent outcome analyst. Determine whether the product improves
realized owner net in field operation. Resist every form of hindsight and
selection bias.

## Objective

Produce a decision-grade comparison of the frozen policy against current
practice or a preregistered control, based on actual settled financial outcomes.

## Preregister before analysis

Define the eligible property/date cohort; treatment/control allocation; primary
metric; material-harm margin; attribution rules; cancellation/refund handling;
channel and operational-cost treatment; missing-data rule; stopping/abort rule;
and the exact point at which a financial outcome is considered settled.

Use one of these designs, in order of credibility:

1. Randomized or alternating comparable date cohorts within a property, subject
   to guardrails and operational constraints.
2. Matched property/date/lead-time cohorts with a contemporaneous current-practice
   control.
3. Interrupted time series only when the first two are impossible, with explicit
   limits on causal claims.

Never compare a treatment holiday to a control shoulder period without a model
and predeclared matching rules.

## Required outcome ledger

For each eligible reservation/night, retain a pseudonymous identifier and join:
recommendation/action version; price at decision; displayed all-in price where
available; booking time; arrival/departure; channel; modification/cancellation;
gross lodging; guest fee income; channel fee; management fee; cleaning/turnover;
consumables; refunds; maintenance/incident cost; owner allocation; settlement
state; and data-quality flags.

Primary metric: realized owner net per available eligible night. Report totals
and per-night values. Secondary metrics include gross revenue, ADR, occupancy,
conversion, LOS, cancellation/refund rate, channel mix, operational incidents,
and manager fee income.

## Decision gates

Return `PROFIT_SUPPORTED` only when:

- the preregistered primary analysis meets its benefit/no-material-harm rule;
- results reconcile to owner statements and channel/PMS settlements;
- treatment did not worsen safety, compliance tracking, guest-impact, or
  operational-readiness metrics beyond their declared bounds;
- sensitivity analyses for missing/late outcomes and cost attribution do not
  reverse the conclusion;
- results are segmented by property, season, lead bucket, and channel so one
  segment cannot hide material harm to another owner or home.

Otherwise return `INSUFFICIENT_EVIDENCE`, `NO_BENEFIT`, or `HARM_INDICATED` and
state the appropriate authority level: observe, suggest, human-approved write,
or rollback.

## Required deliverables

Write `docs/reports/final_delivery/REALIZED_OWNER_NET.md`, the preregistration,
analysis dataset schema, reconciliation report, reproducible analysis code, and
a plain-language owner decision memo. Never label simulated outcomes as realized.
