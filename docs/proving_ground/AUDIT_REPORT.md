# Proving Ground — Audit Report (harness)

## Coverage matrix (stub)

| Module group | Unit | Property | Metamorphic | Lookahead | E2E ladder |
|--------------|------|----------|-------------|-----------|------------|
| moat signals | partial | planned | planned | partial | phase0 |
| pricing core | yes | partial | planned | partial | phase0 |
| proving_ground harness | yes | yes | planned | yes | phase0 |

## Independence record
- Examiner worlds: separate package `proving_ground_exam/`
- Engine grading: deterministic `src/proving_ground/grader.py`
- Auditor LLM sessions: not yet run (Phase C)

## Harness limitations
- Weekly decision cadence in Phase 0
- L2 publishable only after vintages frozen + operator approval

## Reproduce
`uv run pytest tests/proving_ground/ -q`
