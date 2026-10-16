# Prompt 02 — model and simulation proof

You are the independent economic-validation lead. Your task is to select or
reject a pricing policy using V2 only, while preventing calibration leakage and
optimism. Do not make Guesty writes and do not alter a frozen holdout after
viewing it.

## Objective

Find a frozen candidate that is demonstrably no worse than `current_practice`
on simulated owner net, with an evidence trail strong enough to justify shadow
operation. If no candidate meets that standard, reject all candidates and state
the mechanism that prevents release.

## Read first

- `docs/plans/OVERHAUL_2026-10-14.md`
- `config/policies/candidates/pace_learned_owner_net.yaml`
- `proving_ground_exam/market/calibration_v2.yaml`
- `scripts/validate_market_calibration.py`
- current V2 run artifacts and the V2 first-look reports

## Design

1. Freeze an experiment register before tuning: candidate parameters, objective,
   training/screen seeds, untouched evaluation seeds, scenarios, metrics, and
   stop conditions.
2. Use capacity-matched comps and the approved aggregate rate card to validate
   V2. Flag every season/property with insufficient real observations as
   `NOT_MEASURED`; do not silently widen it into a pass.
3. Diagnose the candidate versus `current_practice` by property, season, lead
   bucket, both-sold/only-left-sold outcome, rate, occupancy, owner net, and
   guardrail action.
4. Tune only on the designated screening set. The permitted initial dimensions
   are comp-reference headroom, booking-pace sensitivity, Cloud 9 premium,
   elasticity prior/shrinkage, and holiday treatment. Do not blend a home's own
   current selling price into a reference without a causal design.
5. Freeze the selected candidate, then evaluate it on 25 paired held-out seeds
   against `current_practice`, `property_flat`, and the default engine across
   normal, price-war, demand-collapse, regime-change, holiday-shift, capacity,
   road/resort disruption, supply-surge, and weather stress worlds.
6. Run declared sensitivity overlays for WTP level, holiday uplift, fee salience,
   competitor fees, channel/management fees, turnover cost, and human approval
   rate. Report a policy's failure region, not merely its average.
7. Run recommendation-quality and production-faithful modes separately. The
   latter must model a rate change being withheld when data health is not
   `handle` or an approver does not accept it.

## Required metrics

Primary: paired simulated **owner-net** delta versus current practice.

Secondary: gross revenue, ADR, occupancy, confirmed stays, cancellation-adjusted
net, channel fee, management fee, turnover cost, operational exceptions,
guardrail actions per 1,000 recommendations, peak-ceiling binding share, booking
probability calibration/reliability, and maximum adverse seed/scenario result.

## Promotion gates

A candidate may advance to shadow only when all are true:

- V2 calibration is current and every measured target passes; missing targets are
  disclosed, with a plan to obtain the needed data.
- The held-out paired owner-net interval against `current_practice` does not
  support material harm. Define the material-harm margin before evaluation.
- It has no unacceptable loss in any declared safety/stress scenario, and its
  failure regions are known.
- Its peak price behavior is explained; a ceiling is a safety bound, not the
  mechanism setting virtually all peak prices.
- Booking-probability calibration is measured and acceptable against a defined
  baseline, or the model remains advisory-only.
- All decisions, code, policies, calibration versions, seeds, command lines, and
  artifacts are reproducible outside iCloud.

## Required deliverables

Write `docs/reports/final_delivery/MODEL_EVIDENCE.md`, an experiment manifest,
paired result files, reliability plots/tables, and a candidate decision record:
`ADVANCE_TO_SHADOW`, `REWORK`, or `REJECT`. Do not use `PROMOTE` until prompt 04
passes its integration gates.
