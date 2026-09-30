# Phase 0 — Baseline

Date: 2026-09-29
Branch: `feature/market-sim-and-learning` (from `main` at `3e1b338`, which already contains the audit fixes).

## What was done

Recorded the engine as it stands before the market simulator and the learning flags. Added `--decision-step` on `proving-ground run` so daily cadence is explicit. Default remains 7.

## Files changed

- `src/cli/main.py` — `--decision-step` (default 7) passed into `run_level`.
- `tests/test_proving_ground.py` — `test_proving_ground_cli_decision_step_defaults_weekly`.
- This report.

## Tests

Failing excerpt (before the flag existed):

```
AttributeError: 'Namespace' object has no attribute 'decision_step'
FAILED tests/test_proving_ground.py::test_proving_ground_cli_decision_step_defaults_weekly
```

Passing excerpt:

```
.venv/bin/python -m pytest -q tests/test_proving_ground.py::test_proving_ground_cli_decision_step_defaults_weekly --tb=line
1 passed in 0.28s
```

Full suite:

```
.venv/bin/python -m pytest -q --tb=no
386 passed, 1 deselected in 13.51s
EXIT:0
```

The deselected test is the `@pytest.mark.slow` full-season proving-ground CLI run. The three `tests/test_memory.py` failures described in the 2026-09-29 audit are **not** present on this tree. They were not edited. **Proven.**

## Commands and exit codes

Operator DB was copied, not modified:

```
cp -c data/wp_pricing.db .testrun_runs/market_sim/phase0/eval.db
```

`data/wp_pricing.db` is a symlink to `~/Library/Application Support/wp-price/data/wp_pricing.db`.

Repair, dry run then `--apply` (both exit 0):

```
PYTHONPATH=. .venv/bin/python -m src.cli.main --db .testrun_runs/market_sim/phase0/eval.db repair-bookings
PYTHONPATH=. .venv/bin/python -m src.cli.main --db .testrun_runs/market_sim/phase0/eval.db repair-bookings --apply
```

Both reported `inventory_rows=0`, `pacing_rows=0`, `reservations_rows=0`.

Replay (wrapper exit 0; CLI printed Guesty writes=0). Flags are `--from` / `--to`, not `--start` / `--end`.

```
PYTHONPATH=. .venv/bin/python -m src.cli.main --db .testrun_runs/market_sim/phase0/eval.db \
  replay --from 2026-08-18 --to 2026-09-03 --censor 2026-09-29 \
  --property summit_haus,overlook_ridge,cloud_9 \
  --out .testrun_runs/market_sim/phase0/replay_early
```

16 decision days, 16,111 night-decisions, about 2.2 minutes.

```
PYTHONPATH=. .venv/bin/python -m src.cli.main --db .testrun_runs/market_sim/phase0/eval.db \
  replay --from 2026-09-20 --to 2026-09-29 --censor 2026-09-29 \
  --property summit_haus,overlook_ridge,cloud_9 \
  --out .testrun_runs/market_sim/phase0/replay_clean
```

10 decision days, 10,101 night-decisions.

Proving Ground L1, seeds 1–5, weekly and daily, 3 workers. CLI exit code **1** on every seed because the regret gate failed. That is the baseline, not a crash. `guesty_write_attempts` observed 0 and passed on every manifest.

Property-day timing (`persist=False`, as-of 2026-09-29, 365-day horizon) on the copy:

| Property | Nights priced | Seconds |
|---|---:|---:|
| summit_haus | 327 | 4.770 |
| overlook_ridge | 347 | 4.750 |
| cloud_9 | 334 | 4.448 |

`rate_changes` rows with `result='applied'`: **0** before timing and after both replays.

## Results

### Repair counts versus the audit’s 130 / 30 / 6 / 688 / 42

**Proven:** this database has already been repaired. `data_repairs` holds 764 rows of `booking_contamination_v1`: 722 `pacing_booked_to_available` and 42 `clear_confirmed_at_on_non_sale`. There are **no** inventory rows in that log (no 130 / 30 / 6). A second run is idempotent, which the repair module promises. Reservations are now 106 (audit snapshot was 88), including 47 confirmed non-owner stays, 2 owner confirmed, 40 inquiries, and cancellations. The live calendar was not in the contaminated state the audit counted. **Unknown:** whether inventory was cleaned by a later Guesty sync before the repair, or by a repair whose inventory lines were not retained. The numbers 130 / 30 / 6 are not reproduced here.

### Replay

| Window | Eligible decision-rows | Distinct nights / positives | Per-decision Brier | Dedup Brier | Book rate above / below market |
|---|---:|---:|---:|---:|---|
| Early 08-18..09-03 | 1,339 | 96 / 20 | 0.189 | 0.164 (96 nights) | 13.2% (n=441) / 28.5% (n=898) |
| Clean 09-20..09-29 | 87 | 19 / 6 | unmeasurable | computed 0.262 but below the minimum-n rule | 0% (n=26) / 23.2% (n=56) |

**Proven:** early-window Brier 0.189 and 96/20 match the audit’s repaired + lead-conditioning row (0.188, 96/20). Direction matches the audit’s 13.5% / 28.3% within rounding.

**Suggestive:** the clean window is larger than the audit’s 77 / 17 / 4 because the DB grew. It is still under the calibration minimum. The below-market book rate (23%) is not comparable to the audit’s 6.5% without a matched panel.

**Unknown:** whether the engine beats the market. The audit’s reading stands.

### Proving Ground L1 (expected-RevPAN regret, not realized bookings)

| Cadence | Engine regret, seeds 1–5 | Flat regret |
|---|---|---|
| Weekly | 0.442, 0.446, 0.450, 0.445, 0.454 | 0.145, 0.148, 0.150, 0.145, 0.152 |
| Daily | 0.344, 0.349, 0.350, 0.347, 0.356 | same flat figures (flat does not depend on cadence) |

**Proven:** across seeds 1–5 the engine’s weekly regret stays near the audit’s 45.0% (seed 20260925) and daily regret stays near 35.4%. Flat stays near 14.9%. The level fails. Guesty writes are 0.

**Suggestive:** daily decisions reduce regret versus weekly on this toy world and still lose to flat. That is the inelastic-ceiling behavior (audit M1), not a new measurement of Winter Park.

### Speed

**Proven:** one property-day on the repaired copy is about 4.5–4.8 seconds for 327–347 nights, faster than the audit’s 7.0 seconds for a 365-night case. The calendar simply has fewer nights in the horizon.

## Deviations

- The audit fixes were already committed on `main` (`3e1b338`). There was no dirty `feature/point-in-time-replay` tree to snapshot. This branch starts there.
- iCloud duplicate files (`* 2.py`) were left untracked.
- Replay artifacts and proving-ground run directories stay under `.testrun_runs/` and are not committed.
- L1 CLI exit 1 is the published gate, recorded rather than treated as a broken command.

## Open questions

- Should `creekside_haven`, present in the DB and not in the three-home portfolio brief, stay out of every later run? Phase 2 uses only the three named homes.
- The repair log does not contain the inventory corrections the audit quoted. If the operator still has a pre-repair backup, a recount would close that unknown. Later phases do not depend on those 130 nights still being wrong.
