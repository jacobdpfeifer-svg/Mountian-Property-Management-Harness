# Corrected market-simulation protocol

This protocol is the gate for the next full run and for any candidate policy
tried after it. It keeps the historical pre-correction board separate from the
corrected engine.

## Required baseline run

Run all four policies (`engine`, `flat`, `comp_median`, `tool`) for all 15
scenarios and seeds 1–30 (1,800 jobs), from a committed checkout, into a fresh
directory **outside iCloud Drive**:

```bash
RUN=~/wp-price-runs/market_sim/baseline_$(git rev-parse --short HEAD)
PYTHONPATH=. caffeinate -i .venv/bin/python -m src.cli.main proving-ground market \
  --scenario all --seeds 30 --workers 7 --grid \
  --retain-dbs normal,price_war,holiday_shift \
  --output-dir "$RUN"
```

Do not enable a learning flag during this run.

What the runner guarantees (`src/proving_ground/market_loop.py`):

- `results.jsonl` gets one line per finished job. A crash or sleep loses at
  most the jobs in flight; rerun the same command with `--resume`. Resume
  refuses if the commit, calibration, scenarios, engine policy, seeds, or
  season length changed.
- The first failed job stops the run and writes `failure.json`. No scoreboard
  is written for a failed run.
- An output directory that already holds results is refused without `--resume`.
- `run_config.json` and the manifest's `provenance` block record the commit,
  whether tracked files were dirty, calibration/scenario/policy SHA-256s,
  enabled `models` flags, Python, platform, argv, workers, and timing.
- Retained engine databases key each day's recommendations as
  `run_id = sim-<decision day>`, so a booked night can be traced to the
  recommendation that priced it.
- Retention is per scenario. An engine database is ~80 MB and the others ~20 MB,
  so retaining all 1,800 needs ~60 GB. Three scenarios need ~15 GB. The runner
  refuses to start without 10 GB of headroom.

## Required gates

1. `scripts/audit_market_sim.py <scoreboard> --expect-seeds 30 --expect-scenarios 15`
   exits 0: exactly 1,800 rows, every scenario × policy × seed present once.
2. Provenance shows `models_enabled: []` and `git_dirty: false`.
3. Same-seed determinism passes (`pytest -m slow -k two_full_seasons_stay_deterministic`),
   and content hashes differ across seeds within each scenario/policy.
4. Engine is compared pairwise against flat, comp median, and tool on the same
   scenario and seed.
5. Normal-season engine − flat is reported with its paired bootstrap interval.
6. All four held-out scenarios are present and scored.
7. No policy is called a winner from an unadjusted multi-scenario comparison.
8. The audit JSON is stored beside the scoreboard.

## Required diagnosis before changing policy

Run `scripts/decompose_market_sim.py "$RUN" --scenario <s> --right <flat|comp_median>`
for `normal`, `price_war`, and `holiday_shift`. It reports, per seed mean:
revenue/occupancy/ADR by season, property, and lead bucket; the gap split into
nights both policies sold (price effect) versus nights only one sold (volume
effect); engine share of recommendations at ceiling and floor; and the guardrail
action on each booking day. It reconciles to the scoreboard revenue column.

Determine whether the loss is early/shoulder underpricing, peak pricing pinned
at the ceiling, lower occupancy, guardrail holds, or a combination, and rank
the mechanisms by dollars.

## Candidate policies

- A candidate is a copy of `config/policies/default.yaml` passed with
  `--engine-policy`. The default file is not edited for a trial.
- `models.*.enabled` stays false in every candidate.
- Screen on seeds 1–5, all 15 scenarios, engine only. Pair against the baseline
  with `audit_market_sim.py <candidate scoreboard> --reference <baseline scoreboard>`.
  The reference supplies flat/comp_median/tool rows and the baseline engine as
  `baseline_engine`. It refuses a reference from a different world.
- A confirmation run uses seeds 1–30 and is judged with `--seeds-from 6`, so the
  seeds that picked the candidate do not grade it.
- Do not tune against `normal` alone. Held-out and stress scenarios decide.

## Interpretation

The seasonal flat policy is a benchmark, not automatically the production
policy. A corrected engine result is evidence about this synthetic shopper
world. It is not realized revenue or a causal estimate for Winter Park.

No rate-writing command, `--apply`, or Guesty connection is permitted.
