# Next market-sim run

## Current status (2026-10-09)

**Completed:**

- Combined confirmation: `~/wp-price-runs/market_sim/combined_confirmation_79dae5d/` — report [`docs/reports/market_sim/COMBINED_CONFIRMATION_2026-10-08.md`](../reports/market_sim/COMBINED_CONFIRMATION_2026-10-08.md)
- **Promoted** Cloud 9 / Overlook peak caps into `config/policies/default.yaml` (`property_season_ceiling`)
- Post-promote verification + engine batching: `~/wp-price-runs/market_sim/post_promote_79dae5d/` — report [`docs/reports/market_sim/POST_PROMOTE_2026-10-09.md`](../reports/market_sim/POST_PROMOTE_2026-10-09.md)
- Sensitivity overlays (10 × `normal` × 5 seeds × `--grid`): `~/wp-price-runs/market_sim/sensitivity_79dae5d/`
- Seasonal base anchor (stops the in-season self-reference spiral to the floor): confirmed +$23.3k vs promoted default on `normal` seeds 6–30 (25/25), gap to flat ~−$46k → ~−$23k — report [`docs/reports/market_sim/BASE_ANCHOR_2026-10-09.md`](../reports/market_sim/BASE_ANCHOR_2026-10-09.md). Candidate only; needs owner sign-off on the guard and the base rates.

**Orchestration scripts:** `scripts/post_promote_market_sim.sh`, `scripts/sensitivity_market_sim.sh`, `scripts/confirm_base_anchor_market_sim.sh`

**Next product work (not another 360-job board unless the engine changes):** owner decision on `seasonal_base_anchor_full_shoulder`; then the remaining flat gap, now mostly peak; live shadow/replay against promoted default; owner sign-off before Guesty auto-push.

Simulated revenue is evidence about a synthetic shopper world. Do not call it
realized revenue. Do not write any result to Guesty. Do not edit
`proving_ground_exam/market/calibration.yaml` from held-out or sensitivity results.

## Historical: combined candidate + held-out confirmation

The paired confirmation of
`config/policies/candidates/cloud9_overlook_lower_peak_ceiling.yaml` against the
pre-promote default engine is **done** (seeds 6–30 on six scenarios). The caps
now live in `default.yaml`; the candidate YAML remains for diff-style reruns.

This is a synthetic-market experiment. It must not write rates to Guesty or tune
the simulator from held-out results. Use score-only databases for large boards;
retain only a small normal-world diagnostic sample when property evidence is needed.

Beating the default engine **did not** beat the flat benchmark on `normal`. That
remains true after promotion.

The question for this run is narrow: can property-level pricing close the
Cloud 9 and Overlook Ridge volume gap without giving up peak revenue?

## Leave these alone

- Learning flags stay `enabled: false`. The runner refuses a policy that turns any of them on.
- The point-in-time ceiling stays. Future unsold listed prices are not history.
- Do not change the official shopper world to make the engine look better. Sensitivity files under `config/market_sim/sensitivity/` are separate runs.
- Do not start another 1,800-job board as the next step.

## How a run is isolated

- One market simulation at a time. A second start exits while `~/wp-price-runs/market_sim/RUN.lock` names a live PID.
- Stop that run with `proving-ground market --stop`. That signals the lock owner's PID and its Python children. Do not use `pkill -f "proving-ground market"`.
- If the process dies, rerun the same command with `--resume`. Finished jobs in `results.jsonl` are skipped. A new output directory starts over.
- Databases and logs must be under `~/wp-price-runs/` (or another path outside iCloud). A path inside iCloud is refused.
- Provenance records the commit, tracked dirtiness, the full porcelain status, and every untracked file. `git_dirty` is true when untracked files exist. Resume ignores a change in the untracked list so an iCloud duplicate cannot abort a finished-job resume. A change to tracked file contents (`git_diff_sha256`) still blocks resume.

## Sequence

The five-seed screen below is the historical screening protocol. For the current
work, use the explicit `Exact confirmation run` and `Profiling and batching
follow-up` sections below; they supersede the old five-seed candidate sequence.

Output root: `~/wp-price-runs/market_sim/property_premium_<shortsha>/`.

1. Five-seed diagnostic screen, `normal` only. Engine plus the four continuity policies, the three diagnostic benchmarks (`--diagnostics`), and each property-premium candidate. Retain the `normal` databases.

```bash
RUN=~/wp-price-runs/market_sim/property_premium_$(git rev-parse --short HEAD)
mkdir -p "$RUN"
PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market \
  --scenario normal --seeds 5 --workers 7 --grid --diagnostics \
  --retain-dbs normal --output-dir "$RUN/screen_benchmarks"
```

Candidates, engine only, same five seeds. Pass `--engine-policy` pointing at the files in `config/policies/candidates/`:

- `cloud9_lower_peak_ceiling.yaml`
- `overlook_lower_peak_ceiling.yaml`
- `cloud9_overlook_lower_peak_ceiling.yaml`
- `premium_cap_over_comp.yaml`
- `quality_justified_premium.yaml`

`thin_holiday_ceiling.yaml` is a separate ceiling screen, not part of the property-premium promotion.

```bash
C=cloud9_lower_peak_ceiling
PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market \
  --scenario normal --seeds 5 --workers 7 --policy engine \
  --engine-policy config/policies/candidates/$C.yaml \
  --retain-dbs normal --output-dir "$RUN/screen_$C"
PYTHONPATH=. .venv/bin/python scripts/property_diagnostics.py "$RUN/screen_$C" \
  --scenario normal --engine-policy config/policies/candidates/$C.yaml \
  --md "$RUN/screen_$C/property.md" --json "$RUN/screen_$C/property.json"
```

Audit a candidate against the screen benchmarks:

```bash
PYTHONPATH=. .venv/bin/python scripts/audit_market_sim.py "$RUN/screen_$C/scoreboard.csv" \
  --reference "$RUN/screen_benchmarks/scoreboard.csv" \
  --expect-seeds 5 --expect-scenarios 1 --json "$RUN/screen_$C/audit.json"
```

2. Confirm only a candidate whose five-seed mean beats the screen's engine on `normal` and does not cut peak revenue on Cloud 9 or Overlook in `property.md` (peak occupancy up, peak revenue not down). Confirmation uses seeds 6–30 so the screening seeds do not grade it. Same `--engine-policy`. Audit with `--seeds-from 6`.

3. Full 15-scenario comparison only for a candidate that beat the corrected engine on `normal` in that confirmation and did not worsen `price_war` or `pandemic_collapse` on the way. Held-out scenarios are `holiday_shift`, `den_capacity_cut`, `regime_change`, and `pandemic_collapse`. Retain databases only for `normal`, `price_war`, and `holiday_shift`.

4. Sensitivity, after the engine score from steps 1–3 is written down. One overlay at a time, `normal`, five seeds, engine and flat. Do not retune `calibration.yaml` from the result.

```bash
S=config/market_sim/sensitivity/price_coef_steeper.yaml
PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market \
  --scenario normal --seeds 5 --workers 7 --grid \
  --sensitivity "$S" --output-dir "$RUN/sensitivity_price_coef_steeper"
```

The overlays cover shopper price coefficients, Cloud 9 quality, arrival volume, outside-option utility, and the peak flat benchmark.

## Promotion

A candidate is eligible for the owner to consider only if:

- its confirmation mean (seeds 6–30) beats the corrected engine on `normal`;
- it does not worsen held-out scenarios;
- it does not worsen `price_war` or `pandemic_collapse`;
- Cloud 9 and Overlook peak occupancy move toward the property-specific flat benchmark without a peak revenue loss on those two homes.

`default.yaml` stays as it is until that bar is met and the owner says to change it. `hindsight_oracle.csv` is an upper bound that charges willingness to pay and ignores competitors. It is not a deployable policy.

## Exact confirmation run

Use a new output root outside iCloud. Run the default control and the combined
candidate with the same six scenarios, 30 seeds, and seven workers. Seeds 1–5
provide continuity; the confirmation grade is seeds 6–30.

That is 360 score-only jobs, plus 12 retained diagnostic jobs if Phase 2 is run.
Do not describe this as a 1,800-job full grid.

```bash
set -euo pipefail
export PYTHONPATH=.
ROOT="$PWD"
RUN="$HOME/wp-price-runs/market_sim/combined_confirmation_$(git rev-parse --short HEAD)"
mkdir -p "$RUN"

"$ROOT/.venv/bin/python" -m src.cli.main proving-ground market \
  --scenario normal --seeds 30 --workers 7 --policy engine \
  --output-dir "$RUN/default_normal_1_30"

"$ROOT/.venv/bin/python" -m src.cli.main proving-ground market \
  --scenario normal --seeds 30 --workers 7 --policy engine \
  --engine-policy "$ROOT/config/policies/candidates/cloud9_overlook_lower_peak_ceiling.yaml" \
  --output-dir "$RUN/combined_normal_1_30"
```

Then run the same pair on the held-out and stress set. If `--scenario all`
includes more than the intended scenarios in this checkout, run these five explicitly rather
than silently adding more worlds:

```bash
for SCENARIO in holiday_shift den_capacity_cut regime_change pandemic_collapse price_war; do
  "$ROOT/.venv/bin/python" -m src.cli.main proving-ground market \
    --scenario "$SCENARIO" --seeds 30 --workers 7 --policy engine \
    --output-dir "$RUN/default_$SCENARIO_1_30"

  "$ROOT/.venv/bin/python" -m src.cli.main proving-ground market \
    --scenario "$SCENARIO" --seeds 30 --workers 7 --policy engine \
    --engine-policy "$ROOT/config/policies/candidates/cloud9_overlook_lower_peak_ceiling.yaml" \
    --output-dir "$RUN/combined_$SCENARIO_1_30"
done
```

Audit the normal pair and then repeat the same audit shape for each held-out
scenario:

```bash
"$ROOT/.venv/bin/python" scripts/audit_market_sim.py \
  "$RUN/combined_normal_1_30/scoreboard.csv" \
  --reference "$RUN/default_normal_1_30/scoreboard.csv" \
  --expect-seeds 30 --expect-scenarios 1 --seeds-from 6 --engine-only \
  --json "$RUN/combined_normal_audit_seeds_6_30.json"

for SCENARIO in holiday_shift den_capacity_cut regime_change pandemic_collapse price_war; do
  "$ROOT/.venv/bin/python" scripts/audit_market_sim.py \
    "$RUN/combined_${SCENARIO}_1_30/scoreboard.csv" \
    --reference "$RUN/default_${SCENARIO}_1_30/scoreboard.csv" \
    --expect-seeds 30 --expect-scenarios 1 --seeds-from 6 --engine-only \
    --json "$RUN/combined_${SCENARIO}_audit_seeds_6_30.json"
done
```

For each pair, run the audit using `--seeds-from 6`, and report mean, median,
standard deviation, 95% paired interval, minimum, maximum, candidate wins out
of 25, RevPAN, occupancy, ADR, peak occupancy, and guardrail counts. Retain
only a small normal diagnostic sample if property-level evidence is needed:

```bash
"$ROOT/.venv/bin/python" -m src.cli.main proving-ground market \
  --scenario normal --seeds 6 --workers 2 --policy engine \
  --engine-policy "$ROOT/config/policies/candidates/cloud9_overlook_lower_peak_ceiling.yaml" \
  --retain-dbs normal --output-dir "$RUN/combined_normal_diagnostic"
```

Do not use the diagnostic seed-6 result as the confirmation score.

## Profiling and batching follow-up

Profile one full-season job in one process before changing the engine. Keep
recommendation persistence and choice tracing disabled so the profile measures
the production-like scoring path:

```bash
PROFILE_DIR="$RUN/profiles"
mkdir -p "$PROFILE_DIR"
"$ROOT/.venv/bin/python" - <<PY
import cProfile
from pathlib import Path
from src.proving_ground.market_loop import run_market_job

out = Path("$PROFILE_DIR")
cProfile.runctx(
    "run_market_job('normal', 6, 'engine', db_path=out / 'default.db', "
    "persist_recommendations=False, trace_choices=False)",
    globals(), locals(), str(out / 'default_seed6.prof'))
PY

"$ROOT/.venv/bin/python" - <<PY
import pstats
pstats.Stats("$PROFILE_DIR/default_seed6.prof").strip_dirs().sort_stats("cumulative").print_stats(40)
PY
```

Capture the cumulative time for `generate_recommendations`, feature building,
`compute_ceiling`, seasonal-anchor history, booking-probability/pacing queries,
comp/SQI reads, and SQLite persistence. Do not assume incremental mode is the
solution; the prior audit found only about a 3% full-season improvement.

For each batching optimization:

1. identify the repeated query/calculation and its complete cache key;
2. make one isolated change;
3. run the full pytest suite and compile checks;
4. compare a 60-day before/after run;
5. require identical recommendation fields/content hashes and identical scores;
6. re-profile one full-season job; and
7. only then test it in the seven-worker confirmation board.

The first safe targets are read-only work constant within one recommendation
run: feature inputs, ceiling history panels, comp evidence, seasonal anchors,
demand/SQI inputs, and pacing reference data. Never cache across mutable
decision days unless the decision date and all inventory inputs are in the key.

Verification commands:

```bash
"$ROOT/.venv/bin/python" -m pytest -q
"$ROOT/.venv/bin/python" -m compileall -q src proving_ground_exam scripts
```

The final report must include the exact command matrix, completed-job counts,
the seed-6–30 paired tables, held-out results, retained-database disk usage,
profiles before and after batching, output-equivalence evidence, and a clear
decision: promote for owner review, reject, or gather more evidence.
