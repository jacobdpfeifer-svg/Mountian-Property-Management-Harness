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

**Prior runs under `runs/` that predate `phase0-engine-v2` are invalid** — they used a
synthetic oracle-derived stand-in and must not be cited as evidence.
