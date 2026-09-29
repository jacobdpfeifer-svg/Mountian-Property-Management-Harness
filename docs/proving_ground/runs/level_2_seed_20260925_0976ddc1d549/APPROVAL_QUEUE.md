# Approval Queue

## Fix Card PG-P0-001 — Replace synthetic scoring with point-in-time fixtures

Severity: S2

Finding: Phase 0 now proves the runner, gates, scoreboard, artifact hashing, and receipt surfaces, but Level 2 still uses deterministic public-domain fixture labels rather than as-issued NRCS/NOAA vintages.

Proposed change: add archived source fixtures under `data/proving_ground/` and wire the runner to read them before Level 2 can count as real evidence.

Operator decision: pending

Originating run hash: `0976ddc1d54945308a44edff86ba9be672e3f16e99d8591eaa4963b6b0cab8ab`

