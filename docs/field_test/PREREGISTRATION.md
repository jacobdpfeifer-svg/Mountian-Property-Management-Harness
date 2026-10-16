# Field-test preregistration — DRAFT, INACTIVE

Status: **inactive.** It becomes active only when (1) real Guesty history, settled accounting lines and
owner statements are in the data spine, (2) a candidate's simulation evaluation is PASS, and (3) the plan
below is frozen with `wp-price field-freeze` *before* the first canary night. The frozen file, not this
page, is binding. Draft plan: [`plan.draft.json`](plan.draft.json). Engine: `src/experiments/field.py`.

## Question

Does pricing the treatment nights with the candidate engine raise **settled owner net per eligible
available night** compared with current practice, without material harm to any home or any owner?

The benchmark is current practice (how the homes are priced today), not the default engine.

## Units and assignment

- **Unit:** one home × one block of 7 consecutive nights (Monday–Sunday).
- **Pairing:** consecutive blocks of the same home form a pair (same season, similar demand).
- **Randomization:** inside each pair a coin flip seeded by the frozen plan's SHA-256 picks the
  treatment block. The seed cannot be known before freezing, so nobody can choose favourable weeks.
- **Treatment nights** are priced by the engine through the canary (bounded moves, human-approved).
  **Control nights** keep current practice. Nights outside the plan are not analysed.

Why blocks, not single nights: stays run 3–5 nights and guests compare adjacent dates. Pricing
alternate nights differently would contaminate both arms. Weekly blocks keep most stays inside one arm.
Stays that cross a block boundary are split by night.

## Outcome

`owner net per eligible available night` for each block:

- **Owner net:** from the spine ledger, actual lines only. Lodging + fee income − channel fees −
  payment fees − management fee − cleaning/turnover cost − consumables − maintenance − **refunds**, plus
  damage recovery. Taxes and owner payouts are excluded (pass-through and cash settlement).
- **Allocation:** each reservation's owner net is spread evenly over its nights. Cancellation income
  and refunds stay with the nights they were booked for.
- **Eligible night:** inside the plan window and not removed by an owner block, maintenance or emergency
  constraint. Unsold eligible nights count in the denominator (that is the cost of overpricing).
- **Settlement:** a block is scored only when every stay touching it is settled. Pending money is
  never estimated into the result.

Revenue on the booking day is **not** the metric. Airbnb's own experimentation team showed that
booking-day revenue favours strategies that sell nights faster, and can point the opposite way from the
long-run effect ([Airbnb, CIKM 2023](https://airbnb.tech/wp-content/uploads/sites/19/2023/12/CIKM.pdf)).

## Analysis

- **Estimate:** mean within-pair difference (treatment − control) in owner net per eligible night.
- **Inference:** exact sign-flip randomization test (all 2ⁿ flips up to 12 pairs, else 4,000 fixed
  draws), with the confidence interval obtained by inverting it. Two-sided α = 0.10 (a 90% interval).
  It makes no normality assumption and is valid for any number of pairs. That matters because with three
  homes there are few units.
- **Segments:** each home and each owner (312 + 300 Northwoods = owner A; Cloud 9 = owner B), each
  with its own interval.

## Decision rule (fixed now)

| Verdict | Condition |
|---|---|
| **PROVEN** | portfolio interval lower bound > 0 **and** no home or owner interval reaches below −5% |
| **HARM** | any home or owner interval lies wholly below −5%, the portfolio interval lies wholly below −3%, or a stop rule fired |
| **INCONCLUSIVE** | anything else; the test continues or is extended by a new frozen plan |

Margins: portfolio −3%, segment −5%, as a fraction of the control arm's owner net per eligible night.
They follow the FDA non-inferiority convention (margin = 50% of the smallest effect worth acting on),
loosened from the simulation's 2%/3% because field estimates are far noisier.

**Multiplicity.** Segments are each home, plus each owner with more than one home. Cloud 9's owner is
the same segment as Cloud 9, so it is judged once: k = 4 segments. "Every segment is non-inferior"
(part of PROVEN) is an intersection-union test and uses the nominal α. "Some segment is harmed" is a
union, so HARM uses α/k (Bonferroni). Measured under no true effect (300 simulated plans, `analyse`
itself): false HARM is 0% at 5% block noise, 0.3% at 15% and 2.3% at 40%; false PROVEN is at most 3.3%.

**Minimum length.** An exact test on n pairs cannot reach a p-value below 2/2ⁿ. At α/k = 0.025, that
means **at least 7 pairs (14 weeks) per home** before per-home harm can be shown at all. The draft plan
therefore runs 16 weeks (2027-01-04 .. 2027-04-25, 8 pairs per home). When a segment has too few pairs,
the analysis says so (`harm_note`), and until then the stop rules are the only guard.

## Stop rules (checked weekly with `wp-price field-stop-check`)

Settled money arrives months after the nights, so harm is watched through leading indicators:

1. **Pickup gap:** for upcoming nights, the treatment booked share trails control by more than
   15 points for any home, with ≥ 20 nights compared on each side.
2. **Cancellations:** the treatment cancellation share exceeds control by more than 10 points (≥ 5 stays each).
3. **Operational:** any kill-switch engagement, any read-back mismatch in the canary, any owner complaint.
   The operator records these; the test halts until reviewed.

A fired rule stops new treatment pricing immediately. Treatment nights already priced revert to current
practice through the canary rollback owner.

## Power — read this before expecting a quick answer

Measured on the real 2026-05..10 calendar: weekly revenue per available night varies with a
coefficient of variation of ~0.6 at the Northwoods homes. A plain paired comparison at that noise
detects only effects of about **33% with 60 weeks per arm**. In simulation, even with block noise of
only 15%, a true 10% gain is PROVEN in just 6% of 12-week seasons. A realistic pricing gain of 3–8%
cannot be proven in one season from three homes by this test alone. Therefore:

- The test accumulates across seasons under the same frozen plan family. Every season is reported,
  and the decision rule is applied to the pooled pairs.
- **Pre-specified covariate adjustment** (implemented: `covariate_coefficients` in the plan,
  `analyse(..., covariates=...)`): last year's same-week owner net and the comp-set market index
  (RevPAR-index style, as hotels benchmark against their comp set). The coefficients are estimated on
  pre-period data only and frozen in the plan, so the randomization test stays exact. In the unit test,
  a covariate carrying the demand swing cut the interval to under half its raw width. Covariates may
  be dropped but never added after freezing.
- The real power calculation is redone on the backfilled multi-year history (workstream 4) and
  written into the frozen plan's `analysis` field before freezing.

## What this test does not claim

It does not estimate the effect on nights outside the plan, on other markets, or under a different
candidate. A new candidate code hash or policy needs a new plan.
