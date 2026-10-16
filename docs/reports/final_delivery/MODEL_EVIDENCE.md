# V2 model evidence and decision record

Decision date: 2026-10-15. Decision: **REWORK** — the pace candidate does not
enter evaluation, shadow, or any write path.

## Immutable inputs

| Input | Version / location | Status |
|---|---|---|
| Candidate | `config/policies/candidates/pace_learned_owner_net.yaml`, sha256 `a6faa163de3d…` | Screened only; byte-identical to the screened file |
| Calibration | `proving_ground_exam/market/calibration_v2.yaml`, sha256 `05db7358e511…` | Same file on both screen boards |
| Calibration proof | `~/wp-price-runs/full_sim_20261015_d291c60/v2_calibration_validation.json` | Valid for measured targets |
| Comparator board | `…/v2_screen_benchmarks/` (`current_practice`, normal, seeds 1–5) | Existing artifact |
| Candidate board | `…/v2_screen_pace_learned_owner_net/` (normal, seeds 1–5) | Existing artifact |
| Register | `experiments/EXP-PACE-V2-001.register.json` | Frozen 2026-10-15 |
| Decision ledger | `experiments/decisions.jsonl` | One `screen_decision` entry |

No simulation was run for this record. The decision was computed from the two
existing scoreboards by:

```bash
.venv/bin/python scripts/screen_gate.py \
  --spec docs/reports/final_delivery/experiments/EXP-PACE-V2-001.spec.json \
  --register docs/reports/final_delivery/experiments/EXP-PACE-V2-001.register.json \
  --ledger docs/reports/final_delivery/experiments/decisions.jsonl \
  --candidate-board ~/wp-price-runs/full_sim_20261015_d291c60/v2_screen_pace_learned_owner_net \
  --comparator-board ~/wp-price-runs/full_sim_20261015_d291c60/v2_screen_benchmarks
```

## Screen result (simulated owner net, normal world)

| Seed | Candidate | current_practice | Δ |
|---:|---:|---:|---:|
| 1 | $350,019 | $387,543 | −$37,524 |
| 2 | $316,291 | $324,400 | −$8,109 |
| 3 | $354,450 | $393,760 | −$39,310 |
| 4 | $342,283 | $371,927 | −$29,644 |
| 5 | $340,456 | $345,817 | −$5,361 |

Mean Δ −$23,990; 95% percentile bootstrap −$36,662 … −$11,317; 0 of 5 seeds
favourable. Preregistered material-harm margin: $7,300 (2% of the comparator's
mean simulated owner net, $364.7k). The interval's lower bound is far below
−$7,300, so harm is not excluded → **REWORK**. (An earlier version of this
report called these figures "simulated revenue"; they are simulated owner net.)

## Promotion gates

| Gate | State | Reason |
|---|---|---|
| Calibration current; measured targets pass | PASS with disclosure | Shoulder-season ADR is `NOT_MEASURED` (0 real booked nights). |
| No material simulated owner-net harm vs current practice | FAIL | Screen above. |
| Held-out stress and safety (25 seeds × 9 worlds) | NOT_MEASURED | Closed by the screen gate; not opened. |
| Peak pricing explained | NOT_MEASURED for this candidate | Prior finding (2026-10-14): the shortfall is at peak on price, not volume, mostly Cloud 9. |
| Booking-probability reliability vs base rate | NOT_MEASURED | `src.experiments.reliability` is ready; no candidate forecasts scored. |
| Production-faithful (approval/health withholding) | NOT_MEASURED | Not run for this candidate. |

## What is now enforced in code

- `src/experiments`: a frozen register is content-hashed; screen and evaluation
  seeds must be disjoint; evaluation opens only after a recorded
  `ADVANCE_TO_EVALUATION`, only once, and only if the policy and calibration
  files are unchanged since the freeze.
- Paired bootstrap intervals, failure-region extraction by segment, and a
  reliability table with a base-rate baseline.

## Disclosure

The screen boards existed before the register was frozen, so the screen itself
is not preregistered. The register's value is forward-looking: seeds 6–30 and
the nine evaluation worlds remain unopened for this candidate and cannot be
opened by the tooling without a passing screen.

## Next model step (needs no external input, but must be a new experiment)

A revised candidate (e.g. a different peak treatment) gets a new
`experiment_id`, a new spec frozen before it is screened, and is screened on
seeds 1–5 only. It is screened only when no other market simulation holds the
run lock.
