# Final-delivery evidence ledger

Last reviewed: 2026-10-15 (after the repository-controlled delivery pass). This
ledger is deliberately conservative. Simulated results are never treated as
realized owner profit. An external feed or capability is never inferred from
code or tests. "Fixture" means synthetic, de-identified data built for a test.

States: `PASS` (proven by the cited evidence, for the stated scope only),
`FAIL` (measured and failed), `NOT_MEASURED`, `BLOCKED` (needs an operator,
vendor, payment, real data, or live authority).

Working tree: `~/code/harness` at commit `d291c60` plus the uncommitted changes
listed in `FINAL_ACCEPTANCE_AUDIT.md`. Nothing has been committed or pushed.

## Data

| Claim | Metric | Evidence | Window | Kind | Owner | State | Gate that changes state |
|---|---|---|---|---|---|---|---|
| Versioned, append-only data spine for listing/calendar, reservation lifecycle, ledger, owner statements, market, ops, constraints, price decisions | Checksummed migrations apply once; UPDATE/DELETE refused by trigger; corrections are new versions with `supersedes_id` | `src/db/migrations/0001–0005`, `src/data_spine/`, `tests/data_spine/test_data_spine.py` (28 tests) | fixture | platform test | Data lead | PASS | Re-run on any migration change. |
| Ambiguous identity, money, price basis, or time quarantines | Unknown home, `unknown` or wrong basis, non-USD, negative/NaN money, naive timestamp, inconsistent nights, missing key, out-of-order update → quarantine, never a fact | same tests (parametrized) | fixture | platform test | Data lead | PASS | — |
| PII never enters the spine | Undeclared fields (guest name/email) dropped before validation and before quarantine | `test_pii_is_dropped_by_the_contract`, quarantine payload assertions | fixture | platform test | Data lead | PASS | — |
| A reservation traces decision → modification/cancellation/refund → channel-specific ledger → owner statement | `R-SYN-001` (Airbnb, modified, corrected management fee) reconciles to its statement; VRBO cancellation with partial refund; direct booking with processing fee | `test_trace_from_decision_to_owner_statement`, `test_statements_reconcile_per_channel`, `tests/fixtures/data_spine/synthetic_lifecycle.json` | fixture | platform test | Data lead | PASS (fixture only) | Real settled statements reconcile ≥99% → field PASS. |
| Owner net uses actual statement facts before assumptions | Actual line wins; missing required component → `incomplete`; each assumption named | `test_actual_beats_assumption`, `test_missing_component_is_incomplete_or_labelled_assumed` | fixture | platform test | Data lead | PASS | — |
| Spine migrations applied to the operator database | `schema_migrations` rows on the live DB | none (operator step: `docs/runbooks/DEPLOYMENT.md` §4) | — | platform | Operator | BLOCKED | Operator backs up and applies. |
| Real feeds populate the spine | PMS history, reservation lifecycle, settlements, owner statements, ops records, comp price basis | no approved exports | — | data | Operator / data lead | BLOCKED | `EXTERNAL_REQUESTS.md` items 1–4. |
| Required portfolio data is complete and reconcilable | ≥99% reservation and money reconciliation for the three homes | no real feed | — | data | Data lead / operator | BLOCKED | As above, then a reconciliation dossier. |
| V2 calibration usable for measured targets | 8 measured checks pass; shoulder ADR unmeasured | `~/wp-price-runs/full_sim_20261015_d291c60/v2_calibration_validation.json` | 10 sim seeds; local aggregate rate card | simulated | Model lead | PASS | Re-run if calibration or rate card changes. |
| V2 calibration covers every property/season/lead target | measured coverage | same file: `booked_adr_shoulder_spring` has 0 real nights | — | simulated / aggregate | Data lead | NOT_MEASURED | ≥10 real booked shoulder nights. |

## Model

| Claim | Metric | Evidence | Window | Kind | Owner | State | Gate |
|---|---|---|---|---|---|---|---|
| Experiment register frozen before any evaluation | register hash; disjoint screen (1–5) and evaluation (6–30) seeds; 9 evaluation worlds; harm margin $7,300 | `experiments/EXP-PACE-V2-001.register.json` | — | process | Model lead | PASS (post-hoc for the screen, disclosed) | — |
| Evaluation cannot open without a passing screen or after post-freeze tuning | refused without `ADVANCE_TO_EVALUATION`; refused if policy/calibration hash changed; opens once | `src/experiments`, `tests/security/test_experiments.py` | — | platform test | Model lead | PASS | — |
| Pace candidate no worse than current practice on simulated owner net | paired candidate − current_practice, normal, screen seeds 1–5 | `experiments/decisions.jsonl`: mean −$23,990; 95% bootstrap −$36,662 … −$11,317; 0/5 favourable | normal, seeds 1–5 | simulated screen | Model lead | FAIL → **REWORK** | A new preregistered candidate clears its own screen. |
| Candidate held-out and stress evaluation | 25 paired seeds × 9 worlds | not run (closed by the screen gate) | — | simulated | Model lead | NOT_MEASURED | Only after a screen passes. |
| Booking-probability reliability vs base rate | Brier vs base-rate Brier, binned table | tool built (`src.experiments.reliability`); not run on a candidate | — | simulated | Model lead | NOT_MEASURED | Candidate run with forecasts. |
| Candidate ready for shadow | all Prompt 02 gates | — | — | simulated | Model lead | BLOCKED | Prompt 02 `ADVANCE_TO_SHADOW`; none justified. |

## Platform

| Claim | Metric | Evidence | Window | Kind | Owner | State | Gate |
|---|---|---|---|---|---|---|---|
| Repository quality baseline | default suite, slow lane, mypy, vulture, coverage | 1004 passed / 1 skipped; 10 failures, all the global market-sim lock refusing a second run while the active V2 run holds it; slow 3/3; mypy clean (157 files); vulture clean; coverage 80% (gate 70%) | 2026-10-15 | platform test | Platform lead | PASS (lock caveat) | Re-run the 10 lock-blocked tests when no market sim is running. |
| Clean-environment reproduction | fresh copy, `uv lock --check`, `uv sync --frozen`, same suite | scratch copy: 1004 passed, same 10 lock refusals. The first attempt found a stale `uv.lock` (no `hypothesis`); regenerated, only that package added | 2026-10-15 | platform test | Platform lead | PASS | — |
| Reproducible release manifest | identical `manifest_sha256` on repeat; per-file checksums; policy/calibration/schema/migration/lock hashes | `scripts/release.py`, `tests/platform_ops/test_release.py`; two clean-copy runs printed the same hash | — | platform test | Platform lead | PASS (local) | — |
| Immutable build, activation, rollback | read-only release; atomic `current`; rollback to last verified; tampered release refused | `test_build_activate_rollback`, `test_tampered_release_fails_verification_and_is_skipped_by_rollback` | — | platform test | Platform lead | PASS (local demonstration) | — |
| Production runtime deployed from a verified release | live `DEPLOYED_SHA` equals intended commit | no deployment performed; changes uncommitted | — | platform | Operator | BLOCKED | Commit, build, activate on the operator machine. |
| CI from a clean environment | workflow runs all gates | `.github/workflows/ci.yml` written; never executed on GitHub | — | platform | Platform lead | NOT_MEASURED | Push and observe a green run (pushing to the public repo needs owner approval). |
| Exact three-property scope at sync, webhook, push, review, canary, ingest | unknown listing/property quarantined + audited at each boundary; config must be exactly the three homes | `src/security/scope.py`; `tests/security/test_controls.py`; sync hook in `src/pms/sync.py` | — | platform test | Safety lead | PASS | — |
| Scope at the recommendation and owner-report (audit) paths | out-of-scope home excluded and audited | existing `resolve_property_ids` lock excludes extra listings (`tests/test_guesty.py`), but these paths do not yet call `PortfolioScope` or emit a quarantine event | — | platform test | Safety lead | PASS (exclusion) / NOT_MEASURED (audit event) | Wire `PortfolioScope.filter_properties` into `generate_recommendations` and owner reports (CLI integration owner). |
| Environment and credential separation | env/DB-identity mismatch refused; write credential never falls back to read; secrets never printed | `src/security/environment.py`; tests | — | platform test | Safety lead | PASS (repository) | Operator confirms Guesty can issue a second credential. |
| Secret manager and rotation automation | managed store, automated rotation | none | — | platform | Operator | BLOCKED | Operator selects a service. |
| No secret/PII/confidential file tracked or reported | scanner over tracked + untracked-unignored files | `scripts/scan_repo.py`: 0 problems; its test proves detection | current tree | platform test | Safety lead | PASS (working tree); FAIL (history) | History still holds listing ids; purge needs an owner-approved rewrite and force push. |
| Signed webhook ingress | signature before persistence, replay window, dedupe, receipt, dead letter, scope quarantine, bounded refetch | `src/pms/webhook_ingress.py`; `tests/security/test_webhook_ingress.py` (11) | fixture | platform test | Platform lead | PASS (inactive) | Live subscription: BLOCKED on operator secret + endpoint. |
| Run receipts, degraded modes, incidents, alerts | autonomy only lowers; incident + local alert on injected failure | `src/observability`; tests | — | platform test | Platform lead | PASS (local) | External alert/log service: BLOCKED. |
| Backup and restore | checksum + integrity-checked restore; corruption refused | `test_backup_and_restore_exercise` | — | platform test | Platform lead | PASS (local, unencrypted) | Encrypted off-host retention: BLOCKED. |
| Dependency-aware daily orchestration | missed snapshot stays missing; deadline; retry/backoff; partial ingest; repeat run; lock | `src/orchestration`; chaos tests | — | platform test | Platform lead | PASS (library) | CLI wiring + scheduler cut-over: integration/operator step. |

## Field safety

| Claim | Metric | Evidence | Window | Kind | Owner | State | Gate |
|---|---|---|---|---|---|---|---|
| Global write kill switch, fail-closed, at the final adapter boundary | no HTTP PUT unless scope + separate write credential + production env + unexpired permit + no KILL | `src/security/kill_switch.py`; gate in `GuestyClient.set_rate`; `test_set_rate_never_reaches_http_when_blocked`; 8 parametrized fail-closed cases | — | platform test | Safety lead | PASS | — |
| Ops data can only restrict | `effect='restrict'` enforced by contract and CHECK; booked/blocked never become available; vendor outage → `suggest` | `src/ops/constraint_adapter.py`; tests | fixture | platform test | Ops lead | PASS (fixture) | Real provider records: BLOCKED. |
| Review actions immutable and attributable | role checks, expiry, one decision per item, hash chain, export separating model/human/applied | `src/review`; tests | fixture | platform test | Product lead | PASS (local) | Operator identity provider: BLOCKED. |
| Canary controller inactive, every abort path tested | 29 canary tests incl. kill switch mid-run, read-back mismatch, non-price change, below floor, failed rollback | `src/pms/canary.py`; `tests/security/test_canary.py` | fixture | platform test | Safety lead | PASS (inactive) | — |
| Live writes cannot happen unsafely | the above plus a real canary with read-back | no live canary | — | field | Safety lead / operator | BLOCKED | Written canary authorization (Prompt 04) after shadow passes. |
| Shadow evidence | live read-only recommendations with human decisions | none | — | shadow | Operator | NOT_MEASURED | Shadow run on the live read path. |
| Guesty write authorization exists | written scope | none | — | field safety | Operator | BLOCKED | Operator provides exact scope. |

## Profit

| Claim | Metric | Evidence | Window | Kind | Owner | State | Gate |
|---|---|---|---|---|---|---|---|
| Realized owner net improves | preregistered realized owner net per eligible night | none | — | realized | Outcome analyst / operator | NOT_MEASURED | Prompt 05 preregistration + settled data. |

## Audit notes

- The 10 failing tests in both runs are exactly the market-sim tests that start a
  small simulation and correctly refuse because the active V2 run
  (`v2_default_1_30`) holds `~/wp-price-runs/market_sim/RUN.lock`. They were not
  forced, because that would mean a second concurrent market simulation.
- The pace screen was run before this register existed. Freezing the register
  now cannot make that screen preregistered; it does make the evaluation seeds
  and worlds unopenable without a passing screen.
- Older V1 figures remain regression evidence only.
