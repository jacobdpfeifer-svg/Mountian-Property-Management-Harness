# Prompt 03 — production platform hardening

You are the production engineer and security reviewer. Make the existing system
operable, reproducible, observable, and fail-safe without changing live rates.

## Objective

Close every implementation-controlled gap between a tested repository and a
reliable daily runtime. Produce proof, not design prose.

## Required work

1. **Runtime and deployment:** move the working checkout out of iCloud using the
   supplied non-destructive script; rebuild the environment; make deployment
   reproducible; deploy only reviewed commits; verify `DEPLOYED_SHA` equals the
   intended commit; retain a rollbackable previous runtime.
2. **CI and release integrity:** add a clean-environment pipeline that runs unit,
   ops, slow, type, coverage, dependency, lint/compile, migration, and golden V1
   regression gates. Pin supported Python/dependency versions and publish a
   release manifest with source SHA, policy SHA, calibration SHA, schema version,
   and artifact checksums.
3. **Data/identity controls:** enforce the declared three-property portfolio
   scope everywhere; quarantine unknown listings; distinguish demo, simulation,
   staging, and production databases; use least-privilege read credentials for
   all non-canary tasks; store secrets outside Git and rotate/revoke them safely.
4. **Daily job reliability:** make snapshot, PMS sync, market scrape, signals,
   operations import, recommendation generation, and report generation
   independently observable. Add deadline, retry/backoff, idempotency, structured
   logs, freshness/coverage metrics, alerting, and an explicit degraded-mode
   result for each job.
5. **Data correctness:** finish the connection-hygiene sweep; prevent lock/WAL
   leakage; make every mutation transactional; test DST/timezone behavior;
   preserve observed timestamp precision where the signal needs it; tag comp
   price basis before those observations affect model inputs.
6. **Safety controls:** verify rate floor/ceiling, rounding, move caps,
   peak-blackout, high-side sanity, run-scope, operational-readiness, and health
   gates at the final adapter boundary. Add an immediate global write kill switch
   that fails closed and is exercised in tests.
7. **Operator surface:** generate a daily review artifact containing changes,
   dollar/owner-net rationale, data health, source freshness, guardrail reason,
   operational state, approver decision, and a reversible action record.

## Acceptance gates

- A clean machine can produce an identical release manifest and pass the full
  quality suite.
- Every scheduled job has a documented owner, schedule, deadline, retry policy,
  alert destination, and run receipt.
- An intentionally stale/broken source produces a visible degraded state and no
  broadened authority.
- A simulated malformed price, out-of-scope listing, stale pace record, failed
  write read-back, and rollback each have passing integration tests.
- The deployed runtime proves its version and no secret, PII, raw reservation,
  or confidential rate-card file is tracked by Git or emitted to reports.

## Required deliverables

Create `docs/reports/final_delivery/PLATFORM_READINESS.md`, a deployment runbook,
an incident/rollback runbook, a data-flow diagram, and machine-verifiable
release evidence. Mark every non-built external dependency as `BLOCKED`, never
as an assumed integration.
