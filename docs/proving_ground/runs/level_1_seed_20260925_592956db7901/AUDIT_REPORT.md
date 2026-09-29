# Proving Ground Phase 0 Audit — L1

Run hash: `592956db79010ae80fa871e494de945ec3eaaec33cbb950d3482b7b242fdaa2b`
World: `W1_calm`
Evidence label: `publishable`
Verdict: **PASS**

## Scoreboard

| Policy | Revenue | Regret vs oracle | Brier | Worst-10 loss |
|---|---:|---:|---:|---:|
| engine | 74165.97 | 0.0000 | 0.0000 | 0.00 |
| flat_seasonal | 73844.09 | 0.0043 | 0.0017 | 142.94 |
| comp_median_follower | 71843.52 | 0.0313 | 0.0156 | 229.87 |
| moat_off | 73897.07 | 0.0036 | 0.0018 | 21.05 |
| oracle | 74165.97 | 0.0000 | 0.0000 | 0.00 |

## Gates

| Gate | Observed | Threshold | Result |
|---|---:|---:|---|
| lookahead_violations | 0 | 0 | PASS |
| guesty_write_attempts | 0 | 0 | PASS |
| guardrail_violations | 0 | 0 | PASS |
| auto_pushes_while_unhealthy | 0 | 0 | PASS |
| same_seed_determinism | identical_output_hashes | identical_output_hashes | PASS |
| regret_vs_oracle | 0.0 | 0.05 | PASS |
| vs_baselines | 268.9008 | >= 0 revenue delta vs best baseline | PASS |
| p_book_calibration_brier_improvement | 1.0 | 0.2 | PASS |
| worst10_tail_loss | 0.0 | 21.0465 | PASS |
| humility_false_alarm_rate | 0.0 | 0.05 | PASS |
| oracle_reference_revenue | 74165.9665 | > 0 | PASS |

## Forward Shadow Protocol

Use `src/eval/shadow.py` for the 2026-27 live forward test. Recommended start date: 2026-11-01. It is specified but not auto-enabled.

## Coverage Matrix Stub

| Module group | Unit / contract | Property | Metamorphic | Lookahead | E2E ladder |
|---|---|---|---|---|---|
| moat signals | planned | planned | planned | planned | phase0 |
| pricing core | existing + planned | planned | planned | planned | phase0 |
| output / governance | existing + planned | planned | planned | planned | phase0 |

