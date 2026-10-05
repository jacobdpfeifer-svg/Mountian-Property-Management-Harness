# Operations and compliance audit — 2026-10-05

**Verdict:** A manager can use these systems today as a read-only shadow and human-review aid, but not as proof that a home is legally compliant or that every operational restriction is production-calibrated. The state machine and write boundaries are thoughtfully fail-closed, while the integration and live-source evidence are still too thin for the product pitch. First confirm the portfolio/profile/jurisdiction inputs, then exercise the pipeline with recorded Guesty/vendor fixtures and add stale-feed and pricing-matrix gates.

## Scope and baseline

Audited canonical commit `56a2ffb` from `feature/ops-layer-wip`, in an external worktree.
The iCloud checkout was not audited or edited. Baseline before audit-specific tests was
453 passed, 1 skipped, 2 deselected; after the two seam fixes and tests it is 456 passed,
1 skipped, 2 deselected.

## Findings

| ID | Severity | Component | Summary | Reproduction/evidence | Status |
|---|---|---|---|---|---|
| OPS-001 | P1 | turns | Fixed 24-hour arithmetic ignored Denver DST, mis-sizing turn slack by one hour across the transition. | `tests/ops/test_integration_matrix.py::test_turn_slack_uses_denver_dst_transition`; fall-back now 31h and spring-forward 29h for the tested local window. | fixed |
| OPS-002 | P1 | scope | Unscoped resolver/report/readiness/incident paths could include an undeclared DB home. | Audit test inserts `creekside_haven`; resolver now returns `None`, and unscoped reports/scans use the locked portfolio set. | fixed |
| OPS-003 | P1 | compliance | The checker does not compare booked guest counts or booked nights against jurisdiction caps; it only checks configured permit/listing occupancy. | `src/compliance/__init__.py` has no reservation `guest_count` or night-cap query. | open |
| OPS-004 | P1 | integration | No end-to-end matrix, Guesty replay, forward shadow, or proving-ground ops run existed on the canonical branch. | 64 pre-existing unit tests and code inspection; no `tests/ops/test_integration_matrix.py` before this audit and no ops scenario runner. | partially addressed: seam tests only |
| OPS-005 | P2 | compliance | Rule-pack URLs are disclosed but never fetched or matched to pack requirements by code. Packs are unreviewed. | `check()` only emits a warning for `reviewed_by`; `source_urls` are not opened. Official Fraser page lists safety requirements absent from the pack. | open |
| OPS-006 | P2 | data health | Stale tasks/telemetry/capacity do not fail or demote the data-health gate. | No freshness consumer for ops import runs in `assess_data_health`; a 72-hour stale feed is invisible to autonomy. | open |
| OPS-007 | P2 | adapters | Vendor adapters have no live-tenant verification; Turno public docs are explicitly unverified and CLI coverage is low. | Adapter module docstrings; coverage: Breezeway 57%, Guesty Tasks 68%, Turno 69%. | open |
| OPS-008 | P2 | timezone hygiene | Several CLI/action/normalizer paths still create naive timestamps. | `ruff check src/ops src/compliance` reports 29 findings, including DTZ001/DTZ005/DTZ007/DTZ011. | open |
| OPS-009 | P2 | simulation | `ops_aware_stay` remains off and no measured comparison to the flat baseline exists. | `config/policies/default.yaml`; baseline diagnosis is not present on canonical commit. | open |
| OPS-010 | P2 | receipts | Receipt data is owner-scoped, but profile estimates and unreviewed packs need stronger visible provenance in owner-facing output. | `owner_monthly.py` traces rows but does not render profile basis/rule-pack review state beside every related statement. | open |
| OPS-011 | P3 | tooling | Coverage barely clears threshold and CLI branches are untested. | 70.21% branch coverage; both ops/compliance CLI modules are 0%. | open |
| OPS-012 | P1 | deployment/replay | The copied operator DB has no ops/compliance schema, so the required historical replay cannot start. | On `/Users/jacobpfeifer/wp-price-runs/ops_audit/wp_pricing.db`, `ops report` refused with `no such table: turnover_outcomes` and `compliance check` refused with `no such table: property_credentials`; source and copy hashes remained `6f446d1b94d8aa339db9811e9f087ccfedfff8d87c11256137c742f48bad6f7f`. | open |

## Integration matrix result

The code-level contract is conservative in the reviewed path: `at_risk` demotes
`handle` to `suggest`; `inspection_required` prevents an upward move; and
`out_of_service`/`remediation_in_progress` produce a blocked recommendation rather than
an availability write. Readiness reasons are always-show reasons and include a dollar
contribution. The no-event path returns the ready default.

The full requested 7 × 4 × 4 × 3 compose matrix was **not claimed as executed**: the
canonical repo has no prepared fixture harness for that matrix. This is OPS-004, not a
green result. The new audit tests cover DST, locked scope, and compliance leap-year math;
they do not substitute for the missing compose matrix.

The push boundary drops `min_stay_source == "ops"` and skips blocked/escalated
recommendations in `src/pms/__init__.py`; this was verified by code inspection and the
existing push tests. No Guesty write was attempted.

## Replay and simulation result

The required Guesty-history replay was attempted against a copy of the operator DB,
outside iCloud, for 2026-04-29 through 2026-09-19. It failed closed because the copy
does not contain the operations/compliance tables. No sync or schema write was performed;
the source and copy hashes were unchanged. This means there are no real turn counts,
owner stays, negative-slack counts, or task cross-checks to report.

No ops scenario runner, seeds, scoreboards, or safe copied operator DB were present on
the canonical branch. Therefore there is no honest simulated revenue number to report.
The requested scenarios and measures are specified in `simulation/run_config.yaml` as
an execution contract, with a zero-row placeholder scoreboard rather than fabricated
results. The next run must use 30 paired seeds in the normal world plus two held-out
worlds and compare against the flat baseline.

## Keep / change / replace

| Component | Verdict | Reason |
|---|---|---|
| Turns + slack | **keep, change** | The abstraction is simple and useful at 3–200 homes; use timezone-aware local windows and later add schedule/queue evidence for multi-zone crews. |
| Beta-shrunk readiness probability | **keep, change** | Honest with small samples and disclosed basis; add property/zone hierarchy and freshness/confidence gates. |
| Readiness state machine | **keep** | Explicit evidence, named recovery, and fail-closed expiry fit the autonomy doctrine. Reduce phone UX to a small set of actions later, not the stored history. |
| Incident/action boundary | **keep, change** | Human approval and forbidden actions are strong; broaden structured policy validation and CLI coverage. |
| Vendor adapters | **change** | Keep the normalized contract, but pin recorded official fixtures and verify a tenant before production. Turno is currently an integration proposal. |
| Compliance register | **change** | Keep document/deadline tracking; add jurisdiction-source review records, safety checklist requirements, night/guest cross-checks, and legal-review status. |
| Ops-to-pricing bridge | **change** | Keep restrictions and human escalation; measure gap-night restriction/no-CTA alternatives before enabling stay optimization. |
| Seven readiness states | **keep internally, simplify UI** | The history needs distinct recovery/remediation states; a manager phone flow can expose “risk”, “inspection”, “out of service”, and “verify ready”. |

## Pitch claim check

| Claim | Verdict | Evidence |
|---|---|---|
| Turns are the unit; slack subtracts work, travel, weather buffer. | true with caveat | `src/ops/turns.py`; now DST-aware, but profile numbers are estimates. |
| At risk stops automatic price changes. | true with caveat | Demotes `handle` to `suggest`; suggestions may still be generated. |
| Inspection required blocks increases. | true with caveat | Compose caps recommendation at listed price, with matrix execution still missing. |
| Out of service blocks night and recommends closure, never closes it. | true | Compose status is blocked; action is recommendation only. |
| Disruptions open incidents and require human approval; forbidden actions fail. | true with caveat | `incidents.py`/`actions.py`; affected-set and live fixtures need broader tests. |
| Ops is read-only toward Guesty; signals only lower readiness; named person can mark ready. | true with caveat | Live task creation is separately gated; no live write was exercised in this audit. |
| Compliance has five statuses and never declares compliance. | true with caveat | Code uses the five states, but unverified packs and missing legal cross-checks limit meaning. |
| Guesty Tasks, Breezeway, and Turno are built from public docs. | true with caveat | Module docs say so; Breezeway/Turno are not verified against a live account. |

## Research and official-source checks

Official pages opened on 2026-10-05 include Winter Park’s STR page, Winter Park’s
“Rent Your Home” page, Fraser’s STR page, and Grand County’s STR page. Winter Park’s
page states registration before advertising, advertising of the registration number,
and annual September 30 expiration; Fraser’s page states registration/licensing,
inspection, posted permit, smoke/CO detectors, extinguishers, egress, tax licensing,
and penalties. Those observations are recorded as source-backed audit observations,
not legal advice. See `research/05_compliance_scope.md`.

## Operator decisions needed

1. Confirm the two Northwoods jurisdictions and Cloud 9’s Fraser jurisdiction.
2. Confirm every estimated profile value and the management fee percentages.
3. Name a reviewer for each rule pack and obtain legal review where interpretation is needed.
4. Identify the actual task system and provide a redacted recorded export.
5. Decide whether stale ops feeds should demote autonomy or only raise an operator alert.
6. Approve the paired-seed simulation and a read-only Guesty replay on a copied DB.
