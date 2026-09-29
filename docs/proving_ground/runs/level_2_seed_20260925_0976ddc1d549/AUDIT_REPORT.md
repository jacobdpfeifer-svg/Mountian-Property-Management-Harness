# Proving Ground Phase 0 Audit — L2

Run hash: `0976ddc1d54945308a44edff86ba9be672e3f16e99d8591eaa4963b6b0cab8ab`
World: `W1_median_snow_public_domain_fixture`
Evidence label: `publishable`
Verdict: **PASS**

## Scoreboard

| Policy | Revenue | Regret vs oracle | Brier | Worst-10 loss |
|---|---:|---:|---:|---:|
| engine | 74408.81 | 0.0001 | 0.0000 | 0.70 |
| flat_seasonal | 74063.47 | 0.0047 | 0.0019 | 154.74 |
| comp_median_follower | 72124.37 | 0.0308 | 0.0153 | 231.60 |
| moat_off | 74129.59 | 0.0038 | 0.0019 | 38.62 |
| oracle | 74413.48 | 0.0000 | 0.0000 | 0.00 |

## Gates

| Gate | Observed | Threshold | Result |
|---|---:|---:|---|
| lookahead_violations | 0 | 0 | PASS |
| guesty_write_attempts | 0 | 0 | PASS |
| guardrail_violations | 0 | 0 | PASS |
| auto_pushes_while_unhealthy | 0 | 0 | PASS |
| same_seed_determinism | identical_output_hashes | identical_output_hashes | PASS |
| regret_vs_oracle | 6.3e-05 | 0.1 | PASS |
| vs_baselines | 279.2156 | >= 0 revenue delta vs best baseline | PASS |
| p_book_calibration_brier_improvement | 0.983714 | 0.15 | PASS |
| worst10_tail_loss | 0.6991 | 38.616 | PASS |
| humility_false_alarm_rate | 0.0 | 0.05 | PASS |
| oracle_reference_revenue | 74413.4837 | > 0 | PASS |

## Forward Shadow Protocol

Use `src/eval/shadow.py` for the 2026-27 live forward test. Recommended start date: 2026-11-01. It is specified but not auto-enabled.

## Coverage Matrix Stub

| Module group | Unit / contract | Property | Metamorphic | Lookahead | E2E ladder |
|---|---|---|---|---|---|
| moat signals | planned | planned | planned | planned | phase0 |
| pricing core | existing + planned | planned | planned | planned | phase0 |
| output / governance | existing + planned | planned | planned | planned | phase0 |

