# Final delivery prompt pack

This pack turns the repository into a single evidence-driven delivery program.
It deliberately has **no calendar estimates**. Work advances only when the prior
prompt's acceptance gates are satisfied. A simulated result is never described
as realized owner profit.

## Use order

1. `00_COMMAND_CENTER.md` — maintain the evidence ledger and enforce the gates.
2. `01_DATA_AND_PARTNER_ACQUISITION.md` — obtain the external data and access that
   code cannot create.
3. `02_MODEL_AND_SIMULATION_PROOF.md` — calibrate, select, and stress-test a policy.
4. `03_PRODUCTION_PLATFORM_HARDENING.md` — make the software and integrations
   deployable and observable.
5. `04_SHADOW_CANARY_AND_AUTONOMY.md` — prove the live path without risking a broad
   price change.
6. `05_REALIZED_PROFIT_PROOF.md` — determine whether the product is actually
   improving owner net in the field.
7. `06_IMPLEMENTATION_PROMPT_CATALOG.md` — bounded engineering work orders for
   every in-control platform gap.
8. `07_OPERATOR_OUTREACH_TEMPLATES.md` — copy/paste requests for the people who
   control required data, access, and authorization.

Prompts 02 and 03 may run in parallel after prompt 01 has established the data
contract. Prompts 04 and 05 are blocked by explicit owner authorization where
they involve a real Guesty write or a real pricing experiment.

## Non-negotiable release doctrine

- The release objective is **realized owner net**, not simulated revenue, ADR, or
  occupancy alone.
- `current_practice` is the primary benchmark; beating the old default engine is
  insufficient.
- The current default engine and the current pace candidate must not auto-push
  rates merely because they pass code tests. Their economics must be proven.
- Keep Guesty writes at zero until the canary prompt's explicit authorization and
  read-back/rollback gates are met.
- Keep confidential owner, listing, reservation, and guest data outside the public
  repository. Only approved aggregates may enter `data/exports/`.
- Never tune a simulator on the held-out seeds or scenarios used to judge a policy.
- A missing, stale, malformed, or ambiguously priced data feed must reduce
  autonomy rather than silently producing a confident recommendation.

## Current baseline to preserve

The V2 simulator is the only calibration appropriate for new policy decisions.
It uses all-in guest price and owner-net scoring and has passed its initial
calibration checks, but its real booking samples remain small. The best current
V2 candidate (`pace_learned_owner_net`) is materially better than the default
engine but has not yet beaten `current_practice` in the recorded five-seed normal
screen. That is an open economics problem, not a release result.

The active run root is `~/wp-price-runs/full_sim_20261015_d291c60/`. Treat its
results as pending until its report reconciles commands, artifacts, and scores.
