# Platform readiness — initial assessment

Assessment date: 2026-10-15  
Readiness decision: **FAIL for deployment and canary; PASS only for the tested repository baseline.**

## Proven baseline

The active run records passing isolation, production-preflight, quality,
slow-test, and ops-test gates. Existing code also has portfolio/production-DB
checks, dry-run-oriented write protections, final price boundary validation,
and a non-iCloud deployment script. These are foundations, not release proof.

## Release blockers

| Area | State | Evidence / required correction |
|---|---|---|
| Immutable release and rollback | FAIL | `DEPLOYED_SHA` is absent; deployment can permit dirty bytes and has no atomic prior-runtime rollback or release manifest. |
| CI and clean-environment parity | BLOCKED | No CI workflow or complete clean-machine release evidence. |
| Global write kill switch | BLOCKED | No immediate tested, fail-closed kill switch at the write boundary. |
| Scoped canary controller | BLOCKED | Shell confirmation is not a property/date/approver/move/count-bound authorization. |
| Successful write read-back and rollback | BLOCKED | No tested post-success Guesty/channel read-back, non-price-field check, immutable receipt, or rollback command. |
| Scope and secret controls | FAIL | Sync can ingest unrequested listings; local deployment copies `.env`/token material without rotation/revocation workflow. |
| Daily-job observability | BLOCKED | No unified receipts, deadlines, retries, alerts, degraded mode, or owner/schedule evidence for every required job. |
| Shadow evidence completeness | FAIL | Current shadow records lack immutable model/config hashes, health/readiness, owner-net impact, guardrail, and human-decision lineage. |

## Engineering order

1. Implement and test a global kill switch plus an inactive scoped canary,
   immutable receipt, post-write read-back, non-price-field verification, and
   operator-controlled rollback.
2. Make deployment immutable and rollbackable, add a deterministic release
   manifest and CI parity.
3. Enforce allowlist quarantine at all ingestion boundaries, then add job
   orchestration and fail-closed observability.

No deployment, shadow promotion, or canary is authorized from this assessment.
