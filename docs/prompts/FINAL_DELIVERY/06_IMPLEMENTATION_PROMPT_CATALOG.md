# Prompt 06 — implementation prompt catalog

Use these as independent, bounded work orders. Each assignee must first read the
final-delivery README and Prompt 00, then return: changed files; tests run;
artifacts; data sources; unresolved dependencies; and an explicit `PASS`, `FAIL`,
or `BLOCKED`. No prompt authorizes a Guesty write unless explicitly stated.

## 06A — production foundation and CI/CD

> Build a production foundation for this repository. Replace the laptop/iCloud as
> the sole runtime with isolated `dev`, `staging`, and `production` environments;
> a reproducible container or equivalent immutable runtime; managed durable
> relational storage; encrypted artifact storage; and a scheduler/worker model.
> Add CI that executes unit, integration, ops, slow, type, coverage, security,
> migration, and golden V1-regression gates from a clean environment. Deploy only
> a reviewed immutable release and record source, policy, calibration, schema,
> and dependency hashes. Implement tested rollback to the last verified release.
> Do not migrate production data or make live writes. Pass only with a clean
> build/deploy/rollback demonstration and an architecture decision record.

## 06B — secrets, access, privacy, and portfolio boundary

> Implement secrets management and least-privilege identities. Separate Guesty
> read/sync from any write credential if the account permits. Remove durable
> secrets from local files/token caches, add rotation/revocation procedures,
> secret scanning, and audit logs. Enforce the three-property allowlist at sync,
> webhook, recommendation, audit, and push boundaries; unknown listings must
> quarantine and alert. Add explicit demo/simulation/staging/production identity
> boundaries and PII-minimizing retention/deletion controls. Pass only with
> adversarial tests proving an unknown listing, wrong environment, and missing
> secret cannot produce a write.

## 06C — Guesty webhook ingress and reconciliation

> Implement an HTTPS webhook service following Guesty requirements: validate
> signature before persistence, respond quickly, deduplicate and order-tolerate
> events, persist an immutable receipt, enqueue a bounded re-fetch of
> authoritative Guesty state, and place invalid/unprocessable events in a
> dead-letter workflow. Build periodic full reconciliation because webhooks are
> not a complete calendar-history source. Use no live subscription until the
> operator provides credentials and endpoint authority. Pass with signed fixture,
> duplicate, out-of-order, delayed, malformed, and replay tests.

## 06D — data contracts, provenance, and owner-net ledger

> Implement versioned ingestion contracts and an append-only data spine:
> `fact_reservation_version`, `fact_reservation_night`,
> `fact_calendar_observation`, `fact_financial_ledger`,
> `fact_market_observation`, `fact_ops_task`, `dim_listing_constraint`, and
> `fact_price_decision`. Preserve source hash, source/update/observed times,
> price basis, schema version, and correction lineage. Compute a versioned
> owner-net contribution from actual statement facts, never generic assumed fees
> when actual terms exist. Quarantine ambiguous money, price basis, or identity.
> Pass only when a reservation can reconcile from decision through settlement to
> owner statement and fixtures cover modification, cancellation, refund, and
> channel-specific fee cases.

## 06E — observability, incident response, and disaster recovery

> Build structured logs, a run ledger, metrics, dashboards, and alerts for every
> source/job/write. Include freshness, completeness, coverage, identity mismatch,
> comp degradation, scheduler failure, webhook verification failure, policy/config
> drift, data-health state, write/read-back mismatch, reconciliation exceptions,
> and backup/restore failures. Create severity-based incident and communications
> runbooks, encrypted backup retention, and a tested restore exercise. Pass only
> with injected failures producing an alert, a recorded incident, fail-closed
> autonomy, and a successful restore proof.

## 06F — daily orchestration and data-health recovery

> Replace independent best-effort local jobs with a durable dependency-aware
> orchestration flow for snapshot, PMS sync, comp collection, signals, ops import,
> recommendation, review artifact, and outcome reconciliation. Implement run IDs,
> locks, deadlines, retries/backoff, idempotency, missed-run detection, safe
> recovery, and explicit degraded results. Preserve the fact that a missed daily
> snapshot cannot be invented; do not fabricate pacing history. Pass only after
> chaos tests for a missed snapshot, a slow source, partial ingest, repeated run,
> and database lock demonstrate correct containment.

## 06G — simulator calibration and causal replay

> Build a point-in-time historical replay corpus using frozen first-party calendar,
> reservation, financial, comp, and event vintages. Validate V2 by property ×
> season × lead-time against all-in booked price, booking arrivals, occupancy, LOS,
> cancellations, channel mix, and price-change cadence. Quantify prediction error
> and reliability against naïve/current-practice baselines; label sparse segments
> `NOT_MEASURED`. Freeze calibration before policy evaluation and prevent
> lookahead. Pass only if the world is fit to rank policies by a preregistered
> standard; otherwise report `NOT FIT FOR POLICY RANKING`.

## 06H — held-out policy tuning and sensitivity

> Create an experiment registry with isolated tuning and evaluation seeds and
> scenarios. Tune the pace/elasticity candidate only on screening inputs, then
> freeze it. Evaluate held-out paired owner net against current practice,
> property-flat, and default across normal and declared stress worlds. Sweep WTP,
> holiday uplift, all-in fee salience, competitor fees, demand, cancellation,
> Cloud 9 premium, elasticity, management/channel fees, turn cost, and approval
> rate. Report paired intervals, per-property tails, and failure regions. A policy
> advances only to shadow, never to auto-push, when it meets the precommitted
> non-harm/safety/calibration gates.

## 06I — operations readiness and external provider integration

> Connect the actual cleaning/turn/maintenance/readiness source under a versioned
> data contract. Verify capacity, handoff, maintenance, owner blocks, emergency
> constraints, cost, and service completion against real provider records. Ensure
> an operational restriction can only constrain a rate/booking opportunity and
> cannot make an unavailable night bookable. Produce service-level and exception
> dashboards. Pass with replay and injected-event evidence for over-capacity,
> incomplete turn, incident, cancellation, and vendor outage cases.

## 06J — owner approval and decision-review surface

> Build an operator-facing daily review surface with a complete recommended-change
> queue: current and proposed rate, all-in guest price, expected owner net,
> source freshness, confidence, reasons, guardrails, readiness, assignment arm,
> approver, expiry, and reversible action. Every approve/reject/edit action must
> be immutable and attributable. It must expose the difference between model
> recommendation, human decision, and applied rate. Pass with role tests and an
> exportable audit receipt for every action.

## 06K — scoped Guesty canary and rollback controller

> Build but do not activate a canary controller. It must require an explicit
> property/date allowlist, named approver, max night count, max dollar/percent
> movement, prior-rate snapshot, dry-run diff, idempotency key, final-boundary
> guardrails, post-write Guesty read-back, optional channel-visible verification,
> and automatic rollback/kill switch on any mismatch. It must never change
> availability, blocks, or minimum stays unless that field is separately approved.
> Test every abort path in staging. Activation is blocked until the operator gives
> written live-write authorization for the exact scope.

## 06L — independent final acceptance audit

> Act as an independent auditor. Trace a sample from source ingestion to model
> feature, recommendation, review action, canary receipt, reservation outcome,
> financial reconciliation, and owner report. Reproduce release tests from a
> clean environment; inspect access boundaries, backups, alerts, rollback, data
> quality, simulator evidence, shadow evidence, and field-test preregistration.
> Issue only `ACCEPTED_FOR_SCOPE`, `CONDITIONALLY_ACCEPTED`, or `REJECTED`, listing
> every unresolved condition. `ACCEPTED_FOR_SCOPE` may never mean “profitable”
> unless Prompt 05's realized-owner-net evidence passed.
