# Agent delegation pack

Use this pack after each assignee reads `docs/prompts/FINAL_DELIVERY/README.md`
and `00_COMMAND_CENTER.md`. Each assignee must return changed files, commands
and tests run, artifacts, unresolved dependencies, data sources, and exactly
one of `PASS`, `FAIL`, or `BLOCKED`. No work order authorizes a Guesty write.

## Operating rules

- Do not alter `src/cli/main.py` in parallel. The integration owner adds CLI
  wiring only after the bounded work orders merge.
- Do not edit `src/db/schema.sql` or migrations except as the assigned data
  spine owner. Do not modify policy or calibration files while an economic
  evaluation is frozen.
- Never create fake production data, synthesize a historical snapshot, or put
  secrets, PII, raw reservations, or the confidential rate card in Git.
- Start Wave 1 only after the data-spine interface is approved. Start Waves 2–3
  only after their stated prerequisites. All work remains advisory and
  fail-closed.

## High-reasoning owner work (do not delegate to a low-capability model)

1. **Data-spine architecture (06D).** Own `src/db/schema.sql`, migrations,
   contract interfaces, financial reconciliation semantics, and the append-only
   decision/outcome lineage. This requires decisions about identity, corrections,
   price basis, and actual-versus-assumed owner-net treatment.
2. **Economic proof (06G + 06H).** Freeze the experiment register and material
   harm margin; preserve held-outs; interpret causal replay and reliability;
   decide `REWORK` or `REJECT`. The present candidate fails its five-seed
   current-practice screen and must not be advanced.
3. **Final acceptance (06L).** Independently trace data to settlement only
   after the preceding evidence is complete.

## Wave 0: ready for lower-cost agents in parallel

### Agent A — foundation and CI (06A)

> Implement only the production-foundation work order 06A. Own `infra/`,
> `.github/`, deployment scripts, and `docs/adr/`; do not edit application
> schema, policies, or production data. Design dev/staging/production identity
> separation, an immutable build/release manifest, clean-environment gates,
> and a tested rollback to a prior verified runtime. Existing local deployment
> has no `DEPLOYED_SHA`, so report it as a blocker rather than inventing a
> deployment. Add automated tests/fixtures where possible and finish with the
> required evidence bundle and status.

### Agent B — secrets and boundary controls (06B)

> Implement only 06B. Own `src/security/`, `config/security/`, and
> `tests/security/`. Enforce the three-property allowlist at sync, webhook,
> recommendation, audit, and push boundaries; quarantine and alert on unknown
> listings. Add explicit environment identity checks and missing-secret
> fail-closed behavior, with adversarial tests. Do not put a secret in a fixture,
> edit `src/cli/main.py`, or activate any write credential. Report every
> provider-specific capability that requires an operator as `BLOCKED`.

### Agent C — webhook ingress core (06C)

> Implement only 06C's local, inactive webhook ingress. Own
> `src/pms/webhooks.py`, a new `src/pms/webhook_ingress.py`, and
> `tests/test_webhooks.py`. Validate a signature before persistence, write an
> immutable receipt, deduplicate/order-tolerate events, enqueue an authoritative
> refetch abstraction, and dead-letter invalid events. Provide signed,
> duplicate, out-of-order, delayed, malformed, and replay tests. Do not expose
> a public endpoint, subscribe a real Guesty webhook, or use credentials.

## Wave 1: after the data-spine interface freezes

### Agent D — observability and recovery (06E)

> Implement only 06E, owning `src/observability/` and its tests. Add structured
> local run receipts, metrics/event interfaces, failure-injection evidence, and
> runbooks without connecting external alerting or storage. Every unsupported
> production service must be documented as `BLOCKED`; demonstrate fail-closed
> autonomy on injected source, reconciliation, and write/read-back failures.

### Agent E — durable orchestration (06F)

> Implement only 06F, owning `src/orchestration/` and tests. Create dependency
> aware job state, IDs, locks, deadlines, retries, idempotency, missed-run
> detection, and explicit degraded results for the declared jobs. A missed
> snapshot must stay missing. Do not edit schema/migrations or CLI wiring;
> consume the approved data-spine interface and prove containment with chaos
> tests for lock, partial ingest, slow source, repeat run, and missed snapshot.

### Agent F — operations readiness adapter (06I)

> Implement only 06I, owning `src/ops/` additions and tests. Define an adapter
> boundary for a future approved Turno/Breezeway/Guesty Tasks source and make
> constraints only restrict availability/pricing. Use fixtures; do not connect
> an account. Cover over-capacity, incomplete turn, incident, cancellation, and
> vendor outage; mark missing external credentials and records `BLOCKED`.

## Wave 2: after identity, orchestration, and data-spine integration

### Agent G — daily decision review (06J)

> Implement only 06J, owning `src/review/` and tests. Build a local/exportable
> review queue for recommended versus human versus applied rate, all-in price,
> expected owner net, freshness, guardrails, readiness, assignment, and
> immutable approval/rejection/edit receipts. No web UI or production identity
> is required unless existing project conventions support it. No action may
> result in a live rate write.

### Agent H — inactive canary controller (06K)

> Implement only 06K, owning `src/pms/canary.py` and `tests/test_canary.py`.
> Require exact property/date allowlist, named approver, max movement/count,
> prior snapshot, dry-run diff, idempotency, final-boundary guards, read-back,
> channel verification interface, rollback, and kill switch. Test all abort
> paths in fixtures/staging abstractions. Activation must be impossible without
> an explicit external authorization object; do not create one.

## Final dependency check

No agent may label the product profitable, advance it to shadow, or perform a
write. The high-reasoning owner runs the independent acceptance audit only after
the evidence ledger's data, platform, model, safety, and realized-outcome gates
are satisfied.
