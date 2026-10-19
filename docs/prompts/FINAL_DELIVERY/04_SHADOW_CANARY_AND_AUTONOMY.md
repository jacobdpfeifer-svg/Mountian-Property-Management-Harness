# Prompt 04 — shadow, canary, and autonomy proof

You are the live-operations safety lead. This prompt is the only route toward a
real Guesty write. It is prohibited until the operator supplies explicit written
authorization for the exact scope below.

## Preconditions

- Prompts 01–03 have passed their applicable gates.
- A frozen candidate has `ADVANCE_TO_SHADOW` from prompt 02.
- The production runtime is versioned and the emergency write kill switch is
  tested.
- The operator has named the property, date range, maximum rate change, maximum
  number of nights, approver, rollback owner, and abort conditions.

## Phase A: shadow

Generate recommendations on the live read-only data path. Do not write rates.
For every recommendation, capture the proposed change, current rate, confidence,
data health, operational readiness, expected owner-net impact, guardrail result,
and what a human actually decided. Compare the system's recommendation with the
rate ultimately used and the later reservation/outcome without retrospectively
changing the model.

Shadow passes only when mapping, freshness, calculation, scope, and operator
review evidence are complete; otherwise repair the failed component.

## Phase B: canary

Execute a written, narrow canary only after approval. The canary must:

- use one declared property and explicitly listed dates;
- use a dry-run diff immediately before the live write;
- set a documented max percentage/dollar move and a maximum write count;
- write through the approved adapter only, with idempotency and immutable action
  receipt;
- read the rate back from Guesty and from the channel-visible state where the
  integration allows it;
- confirm availability, min stay, block status, and other non-price fields are
  unchanged;
- support an operator-owned rollback command tested first in a non-production
  environment;
- abort automatically on stale health, scope mismatch, read-back mismatch,
  unexpected channel propagation, operational restriction, or kill-switch state.

## Autonomy ladder

Keep authority explicit and reversible:

`observe` → `suggest` → `human-approved write` → `bounded auto-write`.

Advancement requires evidence at the prior level. A failure moves authority down;
no operator may override a hard safety condition. Operations/compliance data may
restrict a night but must never make an unsafe night bookable.

## Required deliverables

Create `docs/reports/final_delivery/LIVE_SAFETY_EVIDENCE.md`, the signed canary
change request, pre/post rate snapshots, adapter and read-back receipts, rollback
proof, an abort log if applicable, and the explicit authority decision. Do not
claim field profitability here; that belongs only to prompt 05.
