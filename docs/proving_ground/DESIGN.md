# Proving Ground — DESIGN (Phase R checkpoint)

**Status:** Draft for operator approval before Phase B build-out.

## Worlds
- **W1** calm + discrete-choice (`proving_ground_exam/worlds/`)
- **W2** segment mix (stub `w2_segment.py`)
- **W3** empirical resample (stub `w3_resample.py`)
- **W4** adversarial (stub `w4_adversarial.py`)

## Levels L1–L6
Practice specs under `proving_ground_exam/levels/L*/practice/`. Sealed exams: runner-held seed + hashes (Phase B).

## Thresholds
Locked defaults in `src/proving_ground/thresholds.py` — changes require Fix Card.

## Role map (§9)
| Role | Writes |
|------|--------|
| Examiner | `proving_ground_exam/` |
| Runner | `src/proving_ground/`, `data/proving_ground/runs/` |
| Operator | decisions in `APPROVAL_QUEUE.md` |

Isolation: import scan script `scripts/check_proving_ground_isolation.py`; degraded if tool denies unavailable.

## Lockbox
TBD by operator — placeholder hash `lockbox:pending`.

## Effort estimate
- Phase B: 2–3 weeks agent time
- Improvement cycles: ongoing per §10

## Operator questions (unanswered)
See `docs/PROVING_GROUND_PROMPT.md` Phase R checkpoint list.
