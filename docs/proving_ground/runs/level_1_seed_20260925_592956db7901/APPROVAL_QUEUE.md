# Approval Queue

## Fix Card PG-P0-001 — Replace synthetic scoring with point-in-time fixtures

Severity: S2

Finding: Phase 0 now proves the runner, gates, scoreboard, artifact hashing, and receipt surfaces, but Level 2 still uses deterministic public-domain fixture labels rather than as-issued NRCS/NOAA vintages.

Proposed change: add archived source fixtures under `data/proving_ground/` and wire the runner to read them before Level 2 can count as real evidence.

Operator decision: pending

Originating run hash: `592956db79010ae80fa871e494de945ec3eaaec33cbb950d3482b7b242fdaa2b`

