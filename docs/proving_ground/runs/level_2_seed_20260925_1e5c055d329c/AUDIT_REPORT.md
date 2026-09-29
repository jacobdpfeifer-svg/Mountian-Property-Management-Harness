# Proving Ground Phase 0 Audit — L2

Run hash: `1e5c055d329cfc9d0572a3fda123a4530a43911db47d4f3c9c5abdb5a673f9ba`
Engine path: `generate_recommendations`
World: `W1_calm`
Evidence label: `internal_only`
Verdict: **FAIL**

## Scoreboard

| Policy | Revenue | Regret vs oracle | Brier | Worst-10 loss |
|---|---:|---:|---:|---:|
| engine | 55947.36 | 0.2999 | 0.0740 | 3034.18 |
| flat_seasonal | 68159.85 | 0.1471 | 0.0000 | 1268.60 |
| comp_median_follower | 68159.85 | 0.1471 | 0.0000 | 1268.60 |
| moat_off | 55947.36 | 0.2999 | 0.0000 | 3034.18 |
| oracle | 79911.93 | 0.0000 | 0.0000 | 0.00 |

## Gates

| Gate | Observed | Threshold | Result |
|---|---:|---:|---|
| lookahead_violations | 0 | 0 | PASS |
| guesty_write_attempts | 0 | 0 | PASS |
| guardrail_violations | 0 | 0 | PASS |
| auto_pushes_while_unhealthy | 0 | 0 | PASS |
| same_seed_determinism | identical_output_hashes | identical_output_hashes | PASS |
| regret_vs_oracle | 0.299887 | 0.1 | FAIL |
| vs_baselines | -12212.4981 | >= 0 revenue delta vs best baseline | FAIL |
| p_book_calibration_brier_improvement | -4.885872 | 0.15 | FAIL |
| worst10_tail_loss | 3034.1846 | 1268.601 | FAIL |
| humility_false_alarm_rate | 0.0 | 0.05 | PASS |
| oracle_reference_revenue | 79911.9286 | > 0 | PASS |
| world_hardness_flat_vs_oracle | 0.147063 | >= 0.05 | PASS |

## What is still fake or stubbed

- Level 2 NRCS/NOAA as-issued vintages (fixture labels only)
- Humility false-alarm rate (not yet measured from engine uncertainty)
- Independent auditor session

