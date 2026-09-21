# Mont Luxe Collection production-readiness audit — 2026-09-20

## Architect verdict

**Not ready for autonomous production pricing yet.** The deterministic test suite and
the main pricing handoffs are sound, and the amended autonomy grace period is now
implemented. The multi-year ceiling doctrine is reconciled (same-season YoY inside a
five-year lookback; cross-season fallback still forbidden). Production auto-push remains
gated by two unresolved conditions: the Guesty write path has not been exercised against
a safely authorized tenant, and coverage/type/dead-code tooling is not installed in the
runtime environment.

Highest consequence: do not enable a non-dry-run adapter until real three-property
health history is accumulated and a separately authorized single-date Guesty canary has
been completed.

## Step 0 — deterministic pre-pass

| Check | Result | Finding |
|---|---|---|
| Tests | **129 passed** | Four deprecation warnings from `datetime.utcnow()` in `src/signals/store.py`. |
| Coverage | **Unavailable** | `pytest-cov`/`coverage` are not installed; no numeric coverage map can be claimed. |
| Typing | **Unavailable** | mypy/pyright are not installed and no project typing config is present. |
| Dead code | **Unavailable** | vulture/ruff/pyflakes are not installed. |
| Compilation | **Pass** | `compileall` passed for `src/` and `scripts/`. |
| Contract/config preflight | **Pass** | New `scripts/production_preflight.py` passed YAML invariants and ingest → features → ceiling → bookprob → compose handoffs. |
| Dependency audit | **Blocked** | Bundled pip is internally broken (`pip._internal.operations.build` missing), so `pip check` could not run. |

### Stage A — acquisition

**Modules:** `src/ingest`, `src/pms`, `src/scrape`, signal collectors.

**Status:** pass-with-findings. Parsers, sweep validation, explicit scrape status,
idempotent ingestion, Guesty sync, and dry-run adapter tests are present. The stage
correctly fails closed for broken/blocked sweeps. The main open item is operational:
real Guesty sync and real scrape cadence were not run in this audit, and live Guesty
rate writes remain intentionally unexercised.

**Critic challenge:** the fixture sweep proved the validator rejects bad shapes, but
does not prove Airbnb markup drift is detected; retain a periodic real-sweep canary and
keep the fixture tests as regression tests. No dismantle recommendation is supported.

### Stage B — signal processing and scoring

**Modules:** `src/signals`, `src/comps`, `src/resort`.

**Status:** pass-with-findings. Fixture resort and CDOT runs wrote observations; inactive
signals did not bypass the ladder. Comp coverage is explicit and stale/failed rows are
excluded. Signal freshness is folded into the autonomy gate.

**Critic challenge:** the isolated run did not run SNOTEL, weather, or a full scheduled
cycle, so “healthy signal layer” is not proven. A source outage is expected to demote
autonomy, but the three-property production schedule still needs an observed run.

### Stage C — pricing decision

**Modules:** `src/ceiling`, `src/bookprob`, `src/leakage`, `src/elasticity`, `src/compose`.

**Status:** pass-with-critical-open-design. The preflight traced a representative night
through ceiling, booking probability, and compose; recommendations carried both
`P(book|P)` and expected RevPAN, respected floor/bounds, and preserved units. The
existing season-scoped fallback avoided the known cross-season contamination defect.

**Critical open item (resolved in code/docs after this audit):** the operator widened
history from 6–12 months to approximately five years. Ceiling doctrine now uses that
depth as same-season year-over-year pooling (`history_lookback_years`,
`yoy_calendar_window_days`) and still forbids cross-season fallback. The original
open item was to decide explicitly rather than silently keep or drop the prohibition.

**Critic challenge:** tests now cover the amended doctrine (multi-year same-season YoY
and the shoulder-inflation regression) as well as RevPAN mechanics. This stage still
cannot receive a production pass until live three-property history and an authorized
Guesty canary exist.

### Stage D — safety and explainability

**Modules:** `src/guardrails`, `src/explain`, `src/audit`.

**Status:** pass-with-findings. Hard movement caps, blackout nights, sanity floor, run
scope cap, per-night confidence demotion, explainable reasons, and fail-closed health
errors are covered. Implemented in this audit: scoped, asymmetric health grace with a
fail-closed first-run baseline and immediate recovery; regression tests cover transient
failure, sustained failure, and re-arm.

**Critic challenge:** grace-period behavior must be monitored in real run history; a
stale or malformed historical health row is treated as a failure, which is safe but
should alert loudly. No hard invariant was weakened.

### Stage E — output, operations, governance

**Modules:** `src/eval`, `src/db`, `src/cli`, policy YAML, shell schedules.

**Status:** pass-with-findings. CLI sequence, dry-run push, audit/report, owner-scoped
reporting, and launchd scripts were exercised or inspected. The isolated run showed
that `snapshot --verify` requires Guesty-synced property IDs; sample data is not a
production substitute. The audit also exposed placeholder owner names and an existing
`datetime.utcnow()` deprecation warning.

**Critic challenge:** the demo database can show `HANDLE` because its synthetic data is
fresh. This is safe only because the real adapter still requires an explicit choice;
document and enforce that sample/demo databases cannot be mistaken for production.

## Step 2 — integration evidence

Executed on an isolated temporary database:

`init-db → seed-sample → snapshot/backfill → verify → fixture discover-comps → fixture
scrape-comps → health → fixture resort/CDOT signals → promote → recommend → push dry_run
→ audit → report`.

Results: fixture sweep **OK** (280 listings, 5/5 comps, 100% match); health reached
`HANDLE` on synthetic data; recommendations contained booking probability and expected
RevPAN; dry-run attempted no live writes. `snapshot --verify` failed as expected for a
non-Guesty sample database; the post-run audit failed for missing Airbnb room ID,
demand rows, and SNOTEL runs. These are environment/input failures, not a claim that
the pricing math passed production readiness.

## Research synthesis

The design is directionally aligned with established tools: Guesty documents daily
market/history-driven recommendations and warns that same-layer pricing tools can
override each other; PriceLabs documents seasonality, events, lead time, pacing,
custom floors/ceilings, minimum-stay and orphan-gap controls; Beyond documents search
demand, comp sets, minimum stays, gap adjustments, transparent reasons, and audit logs;
AirDNA documents comp-set/market/history-based rates and read-only versus sync modes;
Wheelhouse documents both rule-based and data-driven strategies. These products are
broader and more automated, but their scale-oriented breadth is not automatically
better for three owned houses. The repo’s strongest differentiators are owned-code
RevPAN optimization, explicit evidence health, and hard autonomy guardrails.

Vantry/Vantory lineage was not used as a design assumption; the repository’s current
docs correctly treat Mont Luxe’s architecture as its own design.

## Per-module Architect verdict

| Module/group | Verdict | Rationale |
|---|---|---|
| Acquisition, parsers, collectors | **Improve** | Keep; add real-sweep canary and install deterministic tooling. |
| PMS/Guesty adapter | **Improve** | Keep; complete authorized single-date canary and verify idempotent reconciliation. |
| Comps/resort/signals | **Improve** | Keep; complete real cadence and source-health evidence. |
| Ceiling | **Keep (doctrine reconciled)** | Multi-year same-season YoY; cross-season fallback still forbidden. |
| Bookprob/elasticity/compose | **Keep as-is for current doctrine** | Contract and RevPAN tests pass; revalidate after ceiling decision. |
| Leakage/min-stay | **Improve** | Keep; confirm owner-tunable minimum-stay policy before auto-pushing `minNights`. |
| Guardrails/autonomy | **Fix (done)** | Grace period implemented without changing thresholds or hard invariants. |
| Explain/audit/eval | **Improve** | Keep; add coverage and production evidence lineage. |
| CLI/db/schedules | **Improve** | Keep; strengthen demo/prod separation and operator alerting. |
| Hostaway adapter | **Dismantle not recommended** | Inert interface seam; no production blast radius, but it should remain clearly non-operational. |

## Prioritized punch list

1. **S1 — Resolve and test the multi-year ceiling doctrine.** **Done:** same-season
   YoY pooling inside a 5-year lookback; cross-season fallback remains forbidden;
   regressions cover shoulder inflation and aged-out history.
2. **S1 — Complete a separately authorized Guesty canary.** One property/date, read-back
   verification, dry-run comparison, rollback/abort procedure, and operator approval.
3. **S1 — Establish real three-property health history.** Run sync, pacing snapshot,
   scrape, and signal cadence; verify owner scopes and no missing days before handle.
4. **S1 — Install and run coverage, typing, dead-code, and dependency tooling.** Record
   the triage map; do not infer readiness from 129 passing tests alone.
5. **S2 — Confirm minimum-stay policy values and enablement with the operator.**
6. **S2 — Replace placeholder owner names and eliminate the `datetime.utcnow()` warning.**
7. **S2 — Add an explicit production/demo database marker or guard to prevent synthetic
   sample data from being treated as production health evidence.**

## Critic disposition

The stage reports and integration evidence were challenged against actual code, tests,
and command output. Accepted findings are recorded above. No “pass” claim was accepted
as proof of live Guesty readiness, and no module was dismantled without a downstream
consumer check.
