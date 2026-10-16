# Build-out audit addendum — 2026-10-15

Scope: line-by-line review of the autonomous build's added/modified source,
migrations, safety boundaries, scripts, CI, and focused tests, plus a full-suite
run attempt that respected the existing simulation lock.

## Corrected defects

1. **Release provenance:** `scripts/release.py` had ignored untracked files
   while using `git archive`, allowing a release manifest for an older commit to
   appear valid while omitting uncommitted build-out files. It now refuses every
   tracked or untracked dirty worktree and rejects unexpected files in a release
   directory during verification.
2. **Write credentials:** `GuestyAdapter` previously created its write path with
   the read/sync OAuth client, while the new final boundary correctly demanded a
   distinct write credential. It now creates a separate, non-cached write client
   only after the guarded path is reached. Guesty token caching is disabled by
   default.
3. **Transactional ingestion:** data-spine ingestion previously committed an
   active caller transaction. It now refuses an active transaction rather than
   exposing unrelated uncommitted changes.
4. **Scope evidence:** sync now records an out-of-portfolio quarantine event
   before processing a returned listing, when the append-only audit migration is
   present. Legacy read-only sync compatibility remains unchanged; all pricing
   and live-write boundaries continue to exclude out-of-scope properties.

## Verification after correction

- Focused build-out and affected regression suite: **511 passed**.
- Confidential-file/secret scanner: **0 problems**.
- Full quality and full pytest runs were started and allowed to complete without
  launching a second market simulation. Their expensive lock-sensitive cases
  remain subject to the active simulator's serial-lock rule; no result from a
  blocked market case is treated as a pass.

## Remaining limitations

- The orchestration abstraction cannot forcibly terminate an arbitrary Python
  thread that has exceeded its deadline. It records failure and blocks
  downstream work, but production execution needs an operator-selected
  process/worker runtime for hard cancellation.
- Real deployment, data acquisition, webhook ingress, canary authorization,
  and settled owner-net evidence remain external gates. No Guesty writes were
  made in this audit.
