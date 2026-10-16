# Realized owner net

Date: 2026-10-15. Result: **INSUFFICIENT_EVIDENCE** (nothing measured).
Authority: **observe**.

There is no field cohort, no live decision ledger, and no settled financial
data, so no realized owner-net claim of any kind can be made. Simulated owner
net (V2) is not realized owner net and is not reported here.

## What exists for a future analysis

- Outcome ledger schema: the data-spine tables (`fact_price_decision`,
  `fact_reservation_version`, `fact_reservation_night`, `fact_financial_ledger`,
  `fact_owner_statement`) with pseudonymous keys and lineage.
- `owner_net.v1` per reservation, statement reconciliation, and
  `trace_reservation` (decision → stay → settlement → statement), proven on a
  synthetic fixture only.
- Paired-interval and failure-region tooling in `src/experiments`.

## Preconditions before preregistration (Prompt 05)

A frozen candidate that has passed shadow and a canary; settled data feeds
(`EXTERNAL_REQUESTS.md` items 1–3); a preregistered cohort design, primary
metric, harm margin, settlement point, and missing-data rule, written before
any outcome is examined.
