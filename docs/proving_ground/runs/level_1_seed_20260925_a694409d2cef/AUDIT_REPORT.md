# Proving Ground Phase 0 Audit — L1

Run hash: `a694409d2cef661dea454286da64102f40e06b387d8e294b6c8f46a9332bbefb`
Engine path: `generate_recommendations`
World: `W1_calm`
Evidence label: `internal_only`
Verdict: **FAIL**

## Scoreboard

| Policy | Revenue | Regret vs oracle | Brier | Worst-10 loss |
|---|---:|---:|---:|---:|
| engine | 55690.01 | 0.3035 | 0.0753 | 3279.29 |
| flat_seasonal | 68010.70 | 0.1493 | 0.0000 | 1265.47 |
| comp_median_follower | 68010.70 | 0.1493 | 0.0000 | 1265.47 |
| moat_off | 55690.01 | 0.3035 | 0.0000 | 3279.29 |
| oracle | 79951.35 | 0.0000 | 0.0000 | 0.00 |

## Gates

| Gate | Observed | Threshold | Result |
|---|---:|---:|---|
| lookahead_violations | 0 | 0 | PASS |
| guesty_write_attempts | 0 | 0 | PASS |
| guardrail_violations | 0 | 0 | PASS |
| auto_pushes_while_unhealthy | 0 | 0 | PASS |
| same_seed_determinism | identical_output_hashes | identical_output_hashes | PASS |
| regret_vs_oracle | 0.303451 | 0.05 | FAIL |
| vs_baselines | -12320.6887 | >= 0 revenue delta vs best baseline | FAIL |
| p_book_calibration_brier_improvement | -4.590021 | 0.2 | FAIL |
| worst10_tail_loss | 3279.2919 | 1265.4726 | FAIL |
| humility_false_alarm_rate | 0.0 | 0.05 | PASS |
| oracle_reference_revenue | 79951.3473 | > 0 | PASS |
| world_hardness_flat_vs_oracle | 0.149349 | >= 0.05 | PASS |

## What is still fake or stubbed

- Level 2 NRCS/NOAA as-issued vintages (fixture labels only)
- Humility false-alarm rate (not yet measured from engine uncertainty)
- Independent auditor session

