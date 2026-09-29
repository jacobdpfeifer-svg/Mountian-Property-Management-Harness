# Proving Ground — Lessons

- Synthetic oracle-derived engine prices are an S1 harness failure — always call `generate_recommendations`.
- Full-season daily engine loops are too slow for CI; use short worlds in tests and weekly cadence in Phase 0 runs.
- Pacing replay requires explicit `as_of` filtering — live and replay paths differ.
