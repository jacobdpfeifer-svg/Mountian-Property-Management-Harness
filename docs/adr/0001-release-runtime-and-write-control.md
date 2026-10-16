# ADR 0001 — Release runtime, environments, and live-write control

Status: accepted for the repository; production adoption BLOCKED on operator
infrastructure. Date: 2026-10-15.

## Context

The pricing jobs run from a laptop copy (`~/Library/Application Support/wp-price`)
refreshed by `scripts/deploy_runtime.sh`. There was no immutable release, no
recorded `DEPLOYED_SHA`, no rollback to a verified prior runtime, no CI, no
separation between read and write credentials, and no global write stop. The
GitHub repository is public, so confidential identifiers and data must never be
part of a release.

## Decision

1. **Release = a committed tree.** `scripts/release.py build` exports `HEAD` with
   `git archive` (never the working directory), writes `RELEASE_MANIFEST.json`
   (source commit/tree; sha256 of policy, calibration, schema, migrations, and
   dependency lock; per-file checksums) and `DEPLOYED_SHA`, then makes the files
   read-only. `manifest_sha256` excludes the creation time, so two clean
   machines agree on it.
2. **Activation and rollback are pointer moves.** `current` is a symlink swapped
   atomically; `rollback` re-points to the latest earlier release that still
   verifies. A tampered release is never activated.
3. **Environments are explicit.** `WP_PRICE_ENV` ∈ {demo, simulation, staging,
   production}; unset is `unknown`. A production process may open only a
   database marked production; no other environment may open one.
4. **Writes need four independent things**, checked at the last line before the
   HTTP PUT (`GuestyClient.set_rate`) and again in `push_recommendations` and
   the canary controller:
   - the listing maps to one of the three declared homes;
   - a separate write credential (`GUESTY_WRITE_CLIENT_*`) distinct from the
     sync credential, held by the client making the call;
   - `WP_PRICE_ENV=production`;
   - an unexpired, operator-issued `write_permit.json` naming the property, and
     no `KILL` file in the control directory.
   Any missing or unreadable element blocks the write. No code path creates a
   permit; engaging the kill switch needs no permit.
5. **Schema changes are migrations.** `src/db/migrations/NNNN_*.sql` are
   checksummed and applied explicitly; `init_db` does not apply them, so a daily
   job cannot change the operator database as a side effect.
6. **CI** (`.github/workflows/ci.yml`) runs from a fresh checkout with
   `uv sync --frozen`, an empty control directory, and `WP_PRICE_ENV=simulation`.

## Consequences

- The existing laptop deployment keeps working; adopting `release.py` for it is
  an operator step. A managed runtime, durable managed database, secret manager,
  encrypted artifact store, and alert destination are not built (BLOCKED).
- If Guesty cannot issue a second API credential, live writes stay impossible by
  design until the operator decides how write authority is held.
- Old Git history still contains listing ids; purging it needs a history rewrite
  and force push that only the repository owner can authorize.
