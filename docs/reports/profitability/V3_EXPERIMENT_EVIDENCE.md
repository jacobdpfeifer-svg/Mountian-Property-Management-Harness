# V3 experiment evidence

Date: 2026-10-20. Experiment: `EXP-PACE-V3-001`. Screen decision: **REWORK**. Evaluation: **not opened**. Canary eligibility: **no**.

Held-out seeds 2001–2025 were not run. `open_evaluation` was not called.

## Freeze

Tracked tree was clean (`git status --porcelain --untracked-files=no` printed nothing). Untracked `docs/reports/TESTRUN_FINAL_AUDIT_run2.md` was left in place.

```bash
.venv/bin/python scripts/freeze_experiment.py \
  --spec docs/reports/final_delivery/experiments/EXP-PACE-V3-001.spec.json \
  --register docs/reports/final_delivery/experiments/EXP-PACE-V3-001.register.json \
  --runs-root ~/wp-price-runs
```

- `frozen_at`: 2026-10-20T16:41:18+00:00
- `register_sha256`: `302a3b51dbe6f72d90daf6232ad417fa51d699a9bd0a332e10736932227b9115`
- frozen `code` hash: `55a580de38c07fefd78b9b1a9b459d63b15d52112dba5d56dd96539c6d0ae4c6`
- Candidate and calibration were not edited.
- Market-sim lock was not held.
- No earlier board under `~/wp-price-runs` had used seeds 1001–1005 or 2001–2025.

Profitability code landed after the boards. Current `code` hash is `dc85d0be30adf28d6c527b05e74e32fed3df289c36112a323540636cf66b1fd2`. That hash was not used to run or retune V3. A later board would be a new candidate.

## Screen

Seeds 1001–1005. Scenarios `normal` and `scrape_degraded`. Comparator `current_practice`. Calibration v2. Candidate policy `config/policies/candidates/pace_v3_anchor_repair.yaml` with `--allow-models`.

Boards, outside the repo:

- `~/wp-price-runs/v3_screen_20261020/candidate_normal`
- `~/wp-price-runs/v3_screen_20261020/candidate_scrape_degraded`
- `~/wp-price-runs/v3_screen_20261020/comparator_normal`
- `~/wp-price-runs/v3_screen_20261020/comparator_scrape_degraded`

Scoreboards were concatenated into `candidate_screen` and `comparator_screen` after the code, calibration, and policy hashes matched and `git_dirty_tracked` was false. `run_config.json` on each merged board is the earlier of the two sources. `MERGE_SOURCES.json` names both inputs. First candidate start 2026-10-20T16:41:33Z, after the freeze.

```bash
.venv/bin/python scripts/screen_gate.py \
  --register docs/reports/final_delivery/experiments/EXP-PACE-V3-001.register.json \
  --ledger docs/reports/final_delivery/experiments/decisions.jsonl \
  --candidate-board ~/wp-price-runs/v3_screen_20261020/candidate_screen \
  --comparator-board ~/wp-price-runs/v3_screen_20261020/comparator_screen
```

Ledger entry at 2026-10-20T16:49:14+00:00. Paired simulated owner net, candidate minus current practice, 10 pairs:

- mean −5,031.22
- 95% interval −15,910.70 to +5,848.27
- 3 of 10 pairs favourable
- rationale: lower bound −15,911 ≤ −7,128; harm not excluded

`screen_requires_gain` is true. The screen did not advance. These figures are simulated owner net from the V2 market. They are not settled owner net for the three homes.

No per-property harm table from held-out worlds exists, because evaluation did not open. The screen ledger stores each pair's simulated totals; property splits inside those simulated worlds were not a preregistered screen output and were not graded.

## Comp evidence

No new `market_observation` rows were loaded. Ambiguous price basis still quarantines as `AMBIGUOUS_PRICE_BASIS` (`unknown`, or a reservation priced on a nightly basis). The market template `config/data_mapping/market_observation.template.yaml` has no mapping for an unlabeled total, so an ambiguous export cannot become a usable nightly rate. Existing scrapes stay uncertified and were not promoted into model inputs.

## Tests

Screen gate and freeze behavior are covered by `tests/security/test_experiment_scripts.py` inside the 1113-pass quality-gate run. This screen itself is the artifact in `decisions.jsonl`, not a unit test.

## Assumptions

None added to the candidate, calibration, or spec after the freeze.

## Exceptions

The screen failed its preregistered harm bound. That is the result, not an error in the gate.

## External dependencies

A new candidate, if one is proposed, needs a new spec and a new freeze. This register stays REWORK.

## Next action

Leave `EXP-PACE-V3-001` closed. Do not open seeds 2001–2025 against this register. Do not put this candidate on a canary.
