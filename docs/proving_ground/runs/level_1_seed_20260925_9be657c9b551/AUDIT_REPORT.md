# Proving Ground Phase 0 Audit — L1

Run hash: `9be657c9b5517d7b9e4137cfa774cfeb18e09cc40b5d2b3ab4da2aa6ebf3bf29`
Engine path: `generate_recommendations`
World: `W1_calm`
Evidence label: `internal_only`
Verdict: **FAIL**

## Scoreboard

| Policy | Revenue | Regret vs oracle | Brier | Worst-10 loss |
|---|---:|---:|---:|---:|
| engine | 44154.96 | 0.4477 | 0.1903 | 4658.99 |
| flat_seasonal | 68010.70 | 0.1493 | n/a | 1265.47 |
| comp_median_follower | 68010.70 | 0.1493 | n/a | 1265.47 |
| moat_off | 44154.96 | 0.4477 | n/a | 4658.99 |
| oracle | 79951.35 | 0.0000 | n/a | 0.00 |

## Gates

| Gate | Observed | Threshold | Result |
|---|---:|---:|---|
| lookahead_violations | 0 | 0 | PASS |
| guesty_write_attempts | 0 | 0 | PASS |
| guardrail_violations | 0 | 0 | PASS |
| auto_pushes_while_unhealthy | 0 | 0 | PASS |
| same_seed_determinism | identical_output_hashes | identical_output_hashes | PASS |
| regret_vs_oracle | 0.447727 | 0.05 | FAIL |
| vs_baselines | -23855.733 | >= 0 revenue delta vs best baseline | FAIL |
| p_book_calibration_brier_improvement | -0.973485 | 0.2 | FAIL |
| worst10_tail_loss | 4658.9921 | 1265.4726 | FAIL |
| humility_false_alarm_rate | 0.0 | 0.05 | PASS |
| oracle_reference_revenue | 79951.3473 | > 0 | PASS |
| world_hardness_flat_vs_oracle | 0.149349 | >= 0.05 | PASS |

## What is still fake or stubbed

- Level 2 NRCS/NOAA as-issued vintages (fixture labels only)
- Humility false-alarm rate (not yet measured from engine uncertainty)
- Independent auditor session
- `comp_median_follower` scored exactly like `flat_seasonal` in this world, so it is not an independent baseline (a night with no comp snapshots falls back to the flat price)
- `moat_off` scored exactly like `engine` in this world, so it is not an independent baseline (turning SQI off changed no price)

