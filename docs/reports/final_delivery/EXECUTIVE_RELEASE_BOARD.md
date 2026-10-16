# Executive release board

Reviewed 2026-10-15, after the repository-controlled delivery pass.
Release authority: **observe only**. Guesty writes performed: **0**. No shadow
promotion and no profitability claim.

## 1. What is proven now

- **Data spine (fixture scope):** append-only, versioned facts with
  lineage and quarantine; a synthetic reservation traces from price decision
  through modification, cancellation/refund, and channel-specific settlement to
  a reconciled owner statement. Owner net prefers actual statement facts and
  labels any assumption.
- **Write safety in the repository:** a fail-closed global kill switch checked at
  `GuestyClient.set_rate`; separate write credential; production-only; exact
  three-home scope with quarantine audit at sync, webhook, push, review, canary
  and ingest; an inactive canary whose 29 tests cover
  every abort and rollback path.
- **Platform (local):** reproducible release manifest, immutable build,
  activation and rollback demonstration; signed webhook ingress; run receipts,
  degraded modes, incidents, backup/restore; dependency-aware orchestration
  with chaos tests; review queue with hash-chained, attributable actions.
- **Quality:** 1004 tests pass in the working tree and in a clean copy (10
  further tests refuse because a market simulation holds the run lock); mypy
  and vulture clean; coverage 80%; publish scan clean.
- **Model process:** a frozen register now gates evaluation; it opens only after
  a passing screen and refuses post-freeze tuning.

## 2. What is false or failed now

- The pace candidate does **not** match current practice: simulated owner net
  −$24.0k per season on average over 5 seeds (interval −$36.7k … −$11.3k, 0/5
  favourable). Decision **REWORK**.
- The production runtime is not deployed from a verified release; no
  `DEPLOYED_SHA` exists on the operator machine.
- Old Git history of the public repository still contains listing ids.
- `uv.lock` was stale at `d291c60` (fixed in this pass; uncommitted).

## 3. Next unblocked step

**Prompt 01 — data acquisition**, using `EXTERNAL_REQUESTS.md` items 1–4.
Inputs: de-identified Guesty calendar and reservation history, settlement lines
and owner statements, ops records. Acceptance gate: ingest through the spine
contracts with every quarantine explained and ≥99% reservation/money
reconciliation to owner statements.

In parallel, with no external input: commit this pass (owner decision), then a
**new** preregistered model experiment, screened on seeds 1–5 only when no other
market simulation holds the lock.

## 4. Requires an operator, vendor, payment, or written authorization

Read-only Guesty exports; settlement and statement exports; ops records or
credential; a priced comp sample; webhook secret and endpoint; runtime service
choices; owner approval to push, purge history, and migrate the live DB; and,
only after shadow passes, a separate write credential and a signed canary
scope. Details: `EXTERNAL_REQUESTS.md`.
