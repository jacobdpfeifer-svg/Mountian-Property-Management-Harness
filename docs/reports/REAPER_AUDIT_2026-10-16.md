# Independent Reaper audit — 2026-10-16

**Verdict: REJECTED for profitable/autonomous delivery.**  The repository has a
strong reproducibility and safety baseline, but the only current V2 pricing
candidate is economically below `current_practice`, has no valid frozen
experiment register for further tuning, and contains a production-path
competitor-anchor defect.  Nothing in this report is a realized-profit claim.

## Scope and live-run status

- Audited commit: `d291c60` and the commits after the prior 2026-10-13 report:
  `a2a4183`, `6fdd3c9`, `261ab20`, `c37b2fb`, and `d291c60`.
- The serial V2 full run at
  `/Users/jacobpfeifer/wp-price-runs/full_sim_20261016_d291c60/` was still
  executing `holiday_shift` when this audit was completed.  It owns the market
  simulation lock.  No market simulation, policy change, calibration change,
  or weight tuning was launched by this audit.
- `normal` and `price_war` 30-seed boards in that run are complete; their
  artifacts are provisional until the run script finishes and reconciles all
  declared scenarios.

## What is proven now

- The last full quality baseline passed: **875 passed, 1 skipped, 3 deselected**;
  coverage **78.90%**, plus `mypy`, `vulture`, `pip check`, and `compileall`.
  The operations suite passed **811** tests.  Evidence:
  `full_sim_20261016_d291c60/gate_quality.log` and `ops_tests.log`.
- Focused independent checks passed: `33 passed` across pace pricing, V2 market
  tooling, report tooling, and Cloud 9 comp tests.
- V2 allocation arithmetic is sound: each seasonal segment-share allocation
  sums to exactly **1.000000**; all lead-time, LOS, and channel probability
  vectors normalise correctly before sampling.
- The reproduced five-seed V2 screen confirms the existing decision rather
  than improving it: simulated owner net is **$340,700** for
  `pace_learned_owner_net` versus **$364,689** for `current_practice`
  (**-$23,989 / -6.6%**).  The candidate is better than the legacy default
  engine (**$224,126**) but that is not the release benchmark.  Source:
  `v2_screen_pace_learned_owner_net/results.jsonl` and
  `v2_screen_benchmarks/results.jsonl` in the active run root.

## Weight conclusion

No weight was changed.  That is deliberate and required by the repository's
evaluation doctrine:

- `segments.*.share` is the only arrival-allocation weight; it is correct.
- `segments.*.weights` is not an allocation.  It is an unnormalised exposure
  coefficient in the demand modulator (its total ranges from 0.65 to 1.20).
  Renormalising it would change the calibrated demand response, not repair a
  probability allocation.
- The candidate's decision weights (pace sensitivity 0.30, Cloud 9 premium
  1.05, 1.25 headroom, elasticity priors) cannot be responsibly adjusted now:
  the present candidate already lost its screen and no experiment register
  separates tuning inputs from untouched evaluation inputs.  Retuning from the
  observed screen or the in-progress board would contaminate the result.

## Independent defect found

**High severity — stale/partial competitor scrapes can disable the candidate's
market anchor.**  `src/pricing/pace.py:comp_anchor` chooses the maximum scrape
timestamp across *all* `comp_snapshots` for a stay date, then filters the outer
query to this property's comp set.  If an unrelated comp has a newer scrape,
the property's otherwise valid quotes do not match that timestamp, yielding no
anchor and a silent fallback to the home's own history.

An in-memory adversarial case with two valid home-comp quotes at 2027-01-01 and
one unrelated quote at 2027-01-02 reproduced `(None, 0)` instead of the
expected median.  This is precisely the self-referential fallback the pace
candidate was intended to avoid.  Repair it before any further candidate
evaluation: select the latest valid timestamp *within the property's comp
membership* (and test the partial-scrape case).  Then freeze a new candidate
and experiment register; do not compare a repaired policy to results produced
by the current source hash.

## Delivery position and gates

| Workstream | Position today | Gate to advance |
|---|---|---|
| Model economics | Fail | Repair anchor; preregister a fresh candidate, screen it without evaluation leakage, then run untouched paired V2 evidence against `current_practice`. |
| Simulator calibration | Partial pass | Shoulder booked-ADR remains unmeasured; obtain and reconcile enough real shoulder booking data. |
| Runtime/release | Fail | Demonstrate clean deploy, deployed SHA, immutable manifest, and rollback. |
| Field safety | Blocked | Implement/prove final-boundary kill switch, shadow/canary controls, and obtain written operator authorization. |
| Realized profit | Not measured | Run preregistered field comparison with settled owner-net reconciliation. |

Guesty writes performed by this audit: **0**.
