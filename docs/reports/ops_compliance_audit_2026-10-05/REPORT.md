# Operations and compliance audit

Started 2026-10-05, completed 2026-10-06. Branch `audit/ops-compliance` (from
`feature/ops-layer-wip` @ `56a2ffb`), worktree `~/wp-price-worktrees/ops-audit`.
Prompt: `docs/prompts/OPS_COMPLIANCE_AUDIT_PROMPT.md`.

**Verdict.** A property manager can rely on the pricing boundary today. Across 336
compose cells and every readiness state, ops never raised a price, never granted autonomy,
and never handed a restricted night to the PMS. That boundary only holds because this audit
fixed seven P1 defects, four of them in the readiness state machine. They included a hot-tub
verification that silently cleared a storm restriction, a signal scan that crashed, and UTC
timestamps that let a house be marked ready over an open critical failure. Nothing else is
production evidence. Every cost and probability is an estimate. No task feed exists. The Turno
adapter cannot parse its vendor's documented API. The compliance packs are unreviewed and
were missing fineable life-safety and occupancy rules. In simulation, ops raised no alarm for
crew shortfalls or stale feeds. Before anyone sells this, the operator must confirm the
profiles and the Northwoods jurisdictions, connect one real task source, and have a named
person review the rule packs.

## What was done in this pass

The 2026-10-05 pass inventoried the code and fixed DST and portfolio scoping. It stopped
before the compose matrix, the simulation, the replay, and the critic. This pass did those:

| Stage | Result |
|---|---|
| 1 Inventory | `01_inventory.md`, rewritten. Every ops config key has a reader. Branch coverage rose from 70.2% to 78%. mypy is clean. |
| 2 Components | 17 reproductions in `tests/ops/test_audit_findings.py` and a Hypothesis state-machine test (`tests/ops/test_readiness_properties.py`, 3×3,000 and 1×10,000 examples clean after fixes). |
| 3 Integration | `tests/ops/test_integration_matrix_compose.py`: 7 states × 4 autonomy levels × 4 night types × 3 directions = 336 cells through `recommend_night`, gate on vs off, plus a push seam per state. |
| 4 Simulation | `src/proving_ground/ops_scenarios.py` + `scripts/run_ops_scenarios.py`: 9 scenarios × 3 worlds × 30 seeds × 4 arms (3,240 jobs). Replay of 2026-04-29..09-19 on a copy of the operator DB. Forward shadow specified (`simulation/FORWARD_SHADOW_SPEC.md`). |
| 5 Research | `research/01`–`08`, one per question, plus the rule-pack source check (`05b`) and the vendor field check (`08`). |
| 6 Pitch | Below. |
| 7 Critic | Separate agent; results and disagreements below. |
| 8 Fixes | 18 commits on `audit/ops-compliance`, each with a test that failed before it. |

Hard rules kept: no Guesty writes. The operator DB was copied with SQLite's backup API from
a read-only connection; its SHA-256 was identical before and after
(`96ecf5f5…c4e`), and the copy's hash was unchanged by `ops report` and `compliance check`.
`config/policies/default.yaml` is untouched; policy variants are copies in memory
(`arm_policy`). `proving_ground_exam/` is untouched and the isolation check passes. Nothing
was merged or pushed.

**Not done:** `sync-guesty` was not run. The prompt allows a read-only pull, but it would have
used the operator's production Guesty credentials from this session. The copy already holds
the 2026-10-05 sync, which covers the whole replay window. If the operator wants a fresh
pull first, run it themselves.

## Findings

Severity follows the prompt's scale. "Repro" is the test or command that shows it. All
`tests/...` paths are on this branch.

| ID | Sev | Component | Summary | Repro | Status |
|---|---|---|---|---|---|
| OPS-013 | P1 | readiness | A `verified_ready` for one system (spa) cleared an open restriction from another system (snow-access storm, Dec 20–22) on a different night. Readiness is one log per property. | `test_audit_findings.py::test_verifying_one_system_does_not_clear_another_systems_window` | fixed `fa84ac1` |
| OPS-014 | P1 | readiness | A signal for a night outside an `inspection_required`/`out_of_service` window raised `ReadinessError` and aborted `scan_signal_risk` for every later property. | `::test_signal_outside_an_inspection_window_does_not_abort_the_scan` | fixed `8dc1f66` |
| OPS-026 | P1 | readiness | Regression from the OPS-014 fix, found by Hypothesis: a later automatic `at_risk` could mask an older `inspection_required`/`out_of_service` on the same night, re-allowing upward moves. Where several older rows qualified, the newest won, not the strongest. | `test_readiness_properties.py` (fails on `8dc1f66`) | fixed `f17ddee` |
| OPS-015 | P1 | readiness / time | Stored timestamps were compared as text across offsets. A UTC-stamped critical spa event (18:00 MST) was invisible to a 20:00 local verification, so the house was marked ready over it. | `::test_recovery_sees_a_critical_event_stamped_in_utc` | fixed `3c928d7` |
| OPS-003 | P1 | compliance | No cross-check of booked guest counts against any occupancy limit. | `::test_booked_guest_counts_are_checked_against_the_occupancy_limit` | fixed `aafd4d9` |
| OPS-024 | P1 | compliance packs | The packs silently omitted fineable requirements their own sources state: smoke/CO/extinguisher rows in all three, the Grand County septic cap (design + 2), Fraser's 2-per-bedroom + 4, and Winter Park's parking statement and state sales-tax license. Grand County cited a superseded 2021 §14.8; its fire inspection was wrongly optional. | `research/05b_rule_pack_source_check.md`; `::test_every_rule_pack_entry_names_its_source_and_review_state` | fixed `aafd4d9` (packs still **unreviewed**) |
| OPS-012 | P1 | replay | `ops report` and `compliance check` refused on the real DB (no ops tables, and a `reservations` table without `first_seen_at`), so the Phase 1 shadow could not run. | `::test_ops_report_runs_read_only_on_an_unmigrated_database` (checks file hash) | fixed `9d1c40b`, `aafd4d9` |
| OPS-001 | P1 | turns | Turn slack ignored DST (first pass). | `test_integration_matrix.py` | fixed `3d7d3ef` |
| OPS-002 | P1 | scope | Unscoped ops commands could include the undeclared `creekside_haven` (first pass). | `test_integration_matrix.py` | fixed `3d7d3ef` |
| OPS-027 | P2 | compose | `inspection_required` held the price at a listed price below the floor ($319 vs $375 floor). Push would refuse it, but a person saw it. Now holds at max(listed, floor) and escalates. | matrix: 8 of 336 cells failed before | fixed `00599e3` |
| OPS-028 | P2 | explain | The readiness reason was appended last among pinned reasons, so a tighter reason budget or a fourth pinned reason cut it. | `::test_readiness_reason_is_never_ranked_out` | fixed `5f4c496` |
| OPS-023 | P2* | owner ledger | A ledger row with a misspelled property became an owner-level charge on that owner's statement. An owner/property mismatch was accepted, then vanished from both receipts. No cross-owner leak. | `::test_ledger_rows_never_land_on_the_wrong_owner_or_level` | fixed `b610844` |
| OPS-016 | P2 | readiness | Only `signal`/`telemetry`/`system` counted as automatic, so any other string (e.g. `breezeway`) could mark a house `verified_ready`. Importer and vendor names now count as automatic. Real identity is still missing (OPS-016b). | `::test_automatic_actor_names_outside_the_fixed_set_are_not_trusted` | fixed `c96356e`; identity open |
| OPS-017 | P2 | incidents | A rescan inside a running storm window opened a second incident (the id hashed the window start). | `::test_partial_rerun_inside_a_window_reuses_the_incident` | fixed `5ea9131` |
| OPS-018 | P2 | incidents | A rule listing a forbidden action passed every scan in which it did not fire. | `::test_forbidden_action_in_a_rule_fails_even_without_a_signal` | fixed `c79afa9` |
| OPS-019 | P2 | turns | Overlapping reservations (double booking or stale duplicate) produced ordinary turns with no flag. | `::test_overlapping_reservations_are_reported_not_silently_dropped` | fixed `5e12015` |
| OPS-020 | P2 | capacity | A day with turns and no rostered crew was labelled `unknown`, not `critical`. | `::test_a_day_with_no_rostered_crew_is_critical_not_unknown` | fixed `4e92a13` |
| OPS-021 | P2 | compliance | A fixed-date (09-30) credential issued on 09-30 expired the same day. | `::test_fixed_date_renewal_issued_on_the_renewal_day_lasts_a_year` | fixed `b8c7849` |
| OPS-022 | P2 | sources | `minutes_between` dropped tzinfo when one side had it; late-ready minutes were off by the UTC offset. | `::test_task_minutes_respect_mixed_offsets` | fixed `3c928d7` |
| OPS-025 | P2 | sources | `"250.00 USD"` parsed to None; Guesty UTC task times became next-day service dates. | `::test_vendor_money_and_utc_dates_normalize_locally` | fixed `280330a` |
| OPS-006 | P2 | data health | Stale task, telemetry, or capacity feeds affect nothing. `ops_import_runs` is read only by `ops sources` for display. In simulation a 72-hour stale feed hid a missed clean and raised 0 of 1 needed alarms. | `grep -rn ops_import_runs src/guardrails src/compose` → empty; sim `stale_task_feed` | open (operator decision: demote or alert) |
| OPS-029 | P2 | CLI / shadow | `ops readiness` and the shadow report show the property's latest row; pricing uses the per-night state. The CLI can say at_risk while tonight is priced as ready. | `research/04_readiness_states.md` (repro) | open |
| OPS-030 | P2 | CLI | `ops event add --state …` commits the event before the transition; a refused transition leaves an open critical event that blocks unrelated recovery, and no command resolves it. | `research/04_readiness_states.md` (repro) | open |
| OPS-031 | P2 | telemetry | Spa temperature can only derive `warn`, never `critical`, so a dead hot tub reported without an explicit severity never sets at_risk. | `config/policies/operations.yaml` `telemetry.spa`; `telemetry.derive_severity` | open |
| OPS-032 | P2 | sources | Duplicate aliases silently resolve to the last home listed. | `research/04` / `06` | open |
| OPS-033 | P2 | Turno | The Turno adapter contradicts Turno's published API on 11 fields; a documented list response raises, and a documented completed project is silently dropped. | `research/08_adapter_field_check.md`; `tests/ops/fixtures/vendor_docs/turno_*` | open |
| OPS-034 | P2 | Guesty Tasks | `endTime` is planned, not actual, so `actual_minutes` always equals the plan. The list schema types status and times as objects. | `research/08` | open |
| OPS-035 | P2 | Breezeway | Cost returns the $10.50 materials line, not the $250 clean (`costs[]` read before `rate_paid`). | `research/08` | open (needs a tenant export) |
| OPS-036 | P2 | webhooks | Ordered by arrival, not `updatedAt`/`__v`; a redelivered stale event erased a completion in replay. No signature check, though no receiver is exposed yet. | `research/08` | open; P1 once an endpoint is exposed |
| OPS-037 | P2 | turn model | Slack assumes the whole crew stands in one house; P(ready) never reads capacity; the roster counts one crew in both zones. The simulation found over-capacity days that no ops output flagged as a pricing risk. | `research/02_turn_model.md`; sim | open (redesign proposal) |
| OPS-040 | P2 | readiness / signals | A weather-signal `at_risk` never expires: once its window passes it is fail-closed until a person records `verified_ready`, so every later night stays suggest-only. In simulation the storm left 282 nights restricted with nothing broken, and raised 54 escalations for 9 real needs. This follows the doctrine "expiry is never recovery", which is right for a broken asset but not for a forecast. | sim `storm_road_closure`; `readiness.state_for_night` | open (doctrine decision: let signal-sourced risk clear when the signal is re-read below threshold) |
| OPS-005 | P2 | compliance | Rule-pack sources are not fetched by code. Every entry now names its source and review state, and the loader refuses entries without them. A person must review. | — | partly fixed |
| OPS-007 | P2 | adapters | No live-tenant verification of any adapter. | — | open |
| OPS-010 | P2 | receipt | Owner receipt does not show the estimate basis or the pack's review state beside each statement. | `owner_monthly.py` | open |
| OPS-008 | P3 | time | Remaining naive `datetime.now()`/`date.today()` defaults in CLI paths (ruff DTZ). | `ruff check src/ops` | partly fixed |
| OPS-038 | P3 | replay | Historical turns use current reservation status, so a stay cancelled after `as_of` vanishes from a replay. The table has no cancellation timestamp. | `turns.load_stays` | open; disclosed |
| OPS-039 | P3 | readiness | A heat sensor at 50°F can verify a house as guest-ready (`sensor_verification.heat`). | config | open |
| OPS-011 | P3 | tooling | CLI modules 39–46% covered; ruff 35 findings, mostly cosmetic. | `01_inventory.md` | open |

\* OPS-023 puts a wrong number on an owner's statement. The prompt's scale has no
"wrong owner money" row, so it is P2 here; the critic's view is below.

## Integration matrix

`tests/ops/test_integration_matrix_compose.py` runs all 336 cells through
`recommend_night` on the sample DB, once with `operations.readiness_gate` off and once
on. It reaches each readiness state through legal, evidenced transitions. Each cell asserts:

1. Ops only restricts. The price is never above the gate-off price. It equals it except under
   `inspection_required`. A restricting state never leaves `handle`. **336/336 pass.**
2. at_risk and inspection_required demote handle → suggest. Inspection holds at listed,
   or at the floor when listed is below the floor (then it escalates). out_of_service and
   remediation are `blocked` and `escalate`. **Pass.**
3. No hold lands outside the floor or move cap that the gate-off result respected. **8 cells
   failed before OPS-027; pass now.**
4. The readiness reason is present with its dollar effect. **Pass.** It is now pinned first
   (OPS-028).
5. No restricting state means byte-identical output to gate off (all `Recommendation`
   fields). **Pass for `none`, `ready`, `verified_ready`.**
6. Compose never writes `nightly_inventory`. **Pass.**

Push seam (`test_push_never_writes_a_restricted_night`, 7 states): with health granting
`handle`, no restricted night reaches the adapter. The PMS contract exposes only
`fetch_calendar` and `push_rate`, with no availability or reservation write. Ops-sourced
min-stays are dropped at the write boundary (existing `test_push_never_writes_an_ops_min_stay`).

Data-health seam: stale ops feeds do not affect data health (OPS-006). The capacity view is
not read by compose or P(ready) (OPS-037).

## Replay on the operator DB (2026-04-29 to 2026-09-19, as of 2026-09-19)

These are real reservations, read-only on a copy, with estimated profiles. No task outcomes,
capacity snapshots, readiness events, or profile versions exist in the operator DB, so
**nothing can be said about what actually happened at any turn**. The report says so.

- **Turns:** 24 (Summit Haus 15, Overlook Ridge 8, Cloud 9 1). Four were same-day, all at
  Summit Haus (Jun 18, Aug 29, Aug 31, Sep 4). Three touched owner stays.
- **Negative slack:** none. Minimum slack was 145 minutes (the same-day turns). P(ready)
  ranged 0.93–0.97, all from priors. **Low-readiness turns:** 0.
- **Capacity:** northwoods at 102% (critical) on 2026-06-21 and 2026-08-23, from the roster
  estimate (one 3-person crew).
- **Overlapping reservations:** none. Inquiry (40), canceled (14), and declined (3) rows
  are excluded.
- **Hand cross-check:** the 8 tightest turns were compared with their reservation rows. In
  each, the departing checkout equals the service date and the arriving check-in matches.
  Same-day turns have gap 0.
- **Compliance on the copy (as of 2026-10-06):** no credential register exists, so every
  document is `missing`. The two Northwoods homes are `missing` jurisdiction, with no pack
  applied. Cloud 9's 6 bookings were checked against the Fraser formula limit of 16 (2 per
  bedroom × 6 + 4): none over. That is `unverified`, because the limit comes from an
  unreviewed pack.

## Simulation (SIMULATED: shopper-market world, estimated profiles)

<<SIM>>

## Keep / change / replace

| Component | Verdict | Evidence |
|---|---|---|
| Pricing boundary (compose gate + push) | **Keep** | 336-cell matrix and push seam; Hypothesis invariants after OPS-013/014/015/026. |
| Readiness store and actor rules | **Keep the store, change the surface** | `research/04`: pricing acts on four conditions (OK, Watch, Needs check, Closed). Show the person those four, drop the mandatory `verified_ready → ready` step, write event and transition in one transaction (OPS-030), and take the verifier from a login rather than typed text (OPS-016b). |
| Turn + slack + Beta P(ready) | **Change** | `research/02`: compute slack per crew-day in check-in order; cut five buckets to three; pool by crew; read assignments from the task tool when one exists. Reject queueing models and a home-built dispatcher. Sim: over-capacity days were invisible to pricing. |
| Ops → pricing bridge (`ops_aware_stay`) | see `research/03_ops_pricing_bridge.md` (sim numbers) | <<BRIDGE>> |
| Incidents and actions | **Keep, change triggers** | Forbidden actions are enforced by allowlist and now validated on every scan. Incidents come only from weather/CDOT signals; in simulation a crew no-show, a double-booked crew, and a stale feed raised nothing. |
| Vendor adapters | **Change** | `research/08`: Turno is broken against its docs, Guesty misreads `endTime`, Breezeway misreads cost. Keep the normalized contract; verify against one tenant export before any number is trusted. |
| Compliance register | **Keep the design, change the contents** | `research/05`, `05b`: five statuses, deadlines, and the never-"compliant" rule are right. Packs needed life-safety, occupancy, and septic rows (added, unreviewed) and a named reviewer. |
| Owner receipt | **Change** | Add estimate basis, pack review state, and a readiness-history proof block (`research/07`). |
| Field tooling ambitions | **Replace with integration** | `research/01`, `07`: checklists, photos, linen, and damage claims are what Breezeway, Operto, and Guesty state they sell. Import their outcomes rather than rebuild them. |
| Multi-tenant | **Change: one install per tenant** | `research/06`: config root env var, DB per operator, per-market policy; do not retrofit `tenant_id`. |

## Pitch claim check ("Revenue Engine Pitch for Property Managers", 2026-10-05)

| # | Claim | Verdict | Evidence / fix |
|---|---|---|---|
| 1 | Turns are the unit of work; slack = check-in − checkout − work − travel − weather buffer. | **true with caveat** | `src/ops/turns.py`, DST-correct since OPS-001. Caveat: slack assumes the whole crew in one house, and crew capacity never enters slack or P(ready) (OPS-037). Every minute is an estimate. Reword: "…for each home, from estimated clean times until your task data replaces them." |
| 2 | At risk stops automatic price changes; a person must approve. | **true** (after this audit) | Matrix (all at_risk cells leave `handle`), push seam. Before OPS-013, a spa verification could silently lift a storm at_risk. |
| 3 | Inspection required also blocks price increases. | **true with caveat** | Matrix. Holds at the listed price, or at the floor when listed is below it, and then escalates (OPS-027). |
| 4 | Out of service blocks the night and recommends a closure, but never closes it. | **true** | Matrix: `blocked` + `escalate`. Push seam. The adapter has no availability write. In simulation, closures happen only by the simulated person. |
| 5 | Disruptions open incidents listing arrivals, departures, and turns; a person approves each step; forbidden high-liability actions fail in code. | **true with caveat** | `incidents.py`, `actions.py`, OPS-017/018 fixes. Caveat: only weather and road signals open incidents; crew shortfalls, stale feeds, and asset failures do not (sim). Reword: "Weather and road-closure disruptions open incidents…". |
| 6 | The operations layer is read-only toward Guesty; automatic signals can only lower readiness; only a named person can mark a home ready. | **false as worded** | One gated write exists: Guesty task creation (`actions._create_live_tasks`, behind `--confirm-live-write` and a production DB). Actor names are free text, not identities (OPS-016b). The second half is true (Hypothesis). Reword: "It never writes rates, availability, or reservations. The only write, creating a task, is off unless you turn it on. Automatic signals can only lower readiness, and marking a home ready needs a person's name on the record." |
| 7 | Compliance checks return one of five states and never declare a property compliant. | **true with caveat** | Code and grep. Caveat: the packs are unreviewed, and before OPS-024 they omitted fineable life-safety and occupancy rules. The two Northwoods homes have no jurisdiction, so no rules apply to them yet. |
| 8 | The Guesty Tasks, Breezeway, and Turno connections are built from public docs. | **true but misleading** | They were built from docs, but Turno does not match its own published API (OPS-033), and Guesty and Breezeway each misread a decision field (OPS-034/035). None has been checked against a live account. Reword: "…built from public docs and not yet verified against a live account; Turno support is not working yet." |

## Critic pass

<<CRITIC>>

## Open questions for the operator

1. Which jurisdiction are 312 and 300 Northwoods in (Winter Park town limits or
   unincorporated Grand County), and which fire district? No compliance rule applies to them
   until this is set.
2. Who will review the three rule packs and sign `reviewed_by`? Several entries need
   **operator / legal review**: the Winter Park registration term (page says Sept 30;
   Ord. 552 says 12 months), whether Fraser's booking-tax receipt applies to renewals, and
   the septic design capacity of each Grand County home.
3. Confirm the profile estimates: clean minutes, crew size and roster (is there really one
   3-person crew for both zones?), hot tubs, labor rate, and management fee percentages.
4. Which task system will be the source of truth? A redacted export from it would let
   OPS-033/034/035 be fixed against real data.
5. Should a stale task, telemetry, or capacity feed demote autonomy, or only alert (OPS-006)?
6. Should the pitch keep claim 6 as worded? It is false while the gated task write exists.
7. Do you want a fresh read-only `sync-guesty` before the next replay? This audit did not use
   your Guesty credentials.
