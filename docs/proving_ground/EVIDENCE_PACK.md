# Mont Luxe Collection — Proving Ground Evidence Pack (stub)

SR 11-7 skeleton for customer-facing evidence. **Only `publishable`-labeled runs may be copied into sales materials.**

## 1. What the engine does
Point-in-time pricing for luxury Winter Park inventory using guardrailed RevPAN optimization and explainable recommendations.

## 2. The ladder (ski-run ratings)
Levels L1–L6 from Bunny Hill to Out of Bounds — see `docs/PROVING_GROUND_PROMPT.md` §5.

## 3. What was tested (Phase 0)
- **L1:** synthetic calm season, W1, `cabin_ridge`, engine path `generate_recommendations`
- **L2:** same world + federal vintage tooling (publishable after FIX-P0-001 approved and vintages frozen)

## 4. Data provenance
| Source | Label | Notes |
|--------|-------|-------|
| `data/sample/` | internal_only | Disposable DB bootstrap |
| NRCS AWDB SNOTEL | publishable | After `build-vintages` |
| NOAA CPC ONI | publishable | After `build-vintages` |

## 5. Results
Run manifests under `docs/proving_ground/runs/` — check `evidence_label` per manifest.

## 6. Moat value
Phase B ablation — not yet run.

## 7. Where it lost
Failed level gates are recorded in each run `AUDIT_REPORT.md` (honest failures).

## 8. Safety (L5–L6)
Not yet exercised.

## 9. Live forward test
`src/eval/shadow.py` — recommended start `2026-11-01`, specified not auto-enabled.

## 10. Reproduce
```bash
uv run wp-price proving-ground run --level 1 --seed 20260925
uv run wp-price proving-ground build-vintages
uv run wp-price proving-ground run --level 2 --seed 20260925
```

## What is still fake or stubbed
- Weekly decision cadence (not daily §4.1 yet)
- Humility false-alarm measurement
- Independent auditor sessions
- Sealed exams and lockbox certification
- Customer charts from run data
