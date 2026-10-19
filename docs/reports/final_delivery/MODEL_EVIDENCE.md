# V2 model evidence and decision record

Decision date: 2026-10-15  
Decision: **REWORK** — do not advance to shadow.

## Immutable inputs examined

| Input | Version / location | Status |
|---|---|---|
| Candidate | `config/policies/candidates/pace_learned_owner_net.yaml` | Screened only |
| Calibration | `proving_ground_exam/market/calibration_v2.yaml` | Current for the active run |
| Calibration proof | `~/wp-price-runs/full_sim_20261015_d291c60/v2_calibration_validation.json` | Valid for measured targets |
| Benchmark board | `~/wp-price-runs/full_sim_20261015_d291c60/v2_screen_benchmarks/` | Five-seed normal screen |
| Candidate board | `~/wp-price-runs/full_sim_20261015_d291c60/v2_screen_pace_learned_owner_net/` | Five-seed normal screen |

The candidate board records calibration SHA
`05db7358e51153141906392331db7075970992fc03e9f774750bc101de6d4c07`,
effective policy SHA
`1d6a5db5acaca60b6ce1793391792aafa091f40638de6dc8f13fcf1042fd54bd`, and
commit `d291c60`. Outputs are outside iCloud.

## What the current evidence says

- V2 calibration passes its measured targets. `booked_adr_shoulder_spring`
  remains `NOT_MEASURED` because the aggregate export contains zero qualifying
  real booked nights; this is disclosure, not a calibration pass.
- In the five-seed normal **simulated** screen, the pace candidate's mean
  simulated revenue is about $340.7k versus about $364.7k for
  `current_practice` (approximately -6.6%). The candidate improves over the
  legacy default engine, but that is not the release benchmark.
- The screen has no held-out scenarios, no seeds 6–30 paired result, no
  production-faithful approval-rate evaluation, no candidate reliability
  comparison, and no declared sensitivity failure region.

## Promotion-gate assessment

| Gate | State | Reason |
|---|---|---|
| Calibration is current and measured targets pass | PASS with disclosure | Shoulder-season ADR is still `NOT_MEASURED`. |
| No material simulated owner-net harm versus current practice | FAIL | The normal screen is materially negative; no predeclared harm margin or untouched paired interval exists. |
| Stress and held-out safety | NOT_MEASURED | No V2 candidate stress or held-out evaluation exists. |
| Peak pricing mechanism explained | NOT_MEASURED | No candidate property/lead/guardrail decomposition against current practice exists. |
| Booking-probability reliability versus baseline | NOT_MEASURED | No candidate reliability artifact or acceptance baseline exists. |
| Production-faithful approval/health behavior | NOT_MEASURED | No candidate run with approval withholding/data-health gating exists. |

## Required next experiment, before any additional policy tuning

Create and commit an experiment register that names: the candidate(s) being
screened; tuning inputs; screen seeds; untouched evaluation seeds; scenario
list; a material-harm margin in simulated owner net; policy/calibration/data
hashes; and stop rules. Use the existing five-seed screen only as screening
evidence. Do not open seeds 6–30 or declared held-out worlds for a candidate
that has not cleared the preregistered screen gate.

The present candidate should be rejected from the frozen-evaluation queue until
the data contract and a revised, predeclared candidate are available. A later
candidate may advance only to `ADVANCE_TO_SHADOW`, never to live writes.
