# Proving Ground

This directory holds the deterministic proving-ground harness described in
`docs/PROVING_GROUND_PROMPT.md`.

Phase 0 wires the **real production engine** (`generate_recommendations`) into a
deterministic loop before the full research harness exists:

- seeded Level 1 / Level 2 runs via `proving_ground_exam/worlds/W1_calm`
- engine prices read from `price_recommendations` (not oracle-derived stand-ins)
- measured hard gates with `measured_by` fields
- an engine-vs-baselines scoreboard
- a frozen JSON manifest with a SHA-256 content hash
- an audit report and approval queue with the first Fix Card

Decision cadence defaults to **weekly** (`decision_step_days=7`) for Phase 0 wall-clock
time. Daily stepping is the Phase B target.

Run it with:

```bash
wp-price proving-ground run --level 1 --seed 20260925
wp-price proving-ground run --level 2 --seed 20260925
```

By default, artifacts are written under `docs/proving_ground/runs/`. Pass
`--output-dir <path>` for disposable local runs.

The runner uses `dry_run` only — Guesty write attempts are measured from `rate_changes`.
Level 2 still needs as-issued NRCS/NOAA fixtures under `data/proving_ground/vintages/`;
that work is tracked in the generated approval queue.

## Shopper market

`proving-ground market` scores the same pricing engine against synthetic shoppers.
The world lives in `proving_ground_exam/market/` and does not import the engine.
The driver is `src/proving_ground/market_loop.py`. W1 is unchanged.

```bash
PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market \
  --scenario normal --seeds 1 --workers 1 --policy flat \
  --output-dir .testrun_runs/market_sim/runs
```

`--scenario all` runs the 15 Winter Park scenarios. Four of them are held out
and are scored, not used to change calibration: `holiday_shift`,
`den_capacity_cut`, `regime_change`, `pandemic_collapse`. `--max-days 0` keeps
the full season. `--incremental` is off unless you pass it; a booking changes
the property digest, so it usually does not skip nights.

Learning flags live under `models:` in `config/policies/default.yaml`. They
default to off. Reports are in `docs/reports/market_sim/`.

Telluride is a portability file, not a 16th scenario:
`proving_ground_exam/market/portability/`. `load_resort_config()` still reads
Winter Park.

**Prior runs under `runs/` that predate `phase0-engine-v2` are invalid** — they used a
synthetic oracle-derived stand-in and must not be cited as evidence.
