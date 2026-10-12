# Operations Layer and Compliance Register: Audit, Integration Test, and Redesign Review

**What this is:** a standing prompt for a fresh session or a lead agent with sub-agents. Feed it
whole. It audits the operations layer (`src/ops/`) and the compliance register
(`src/compliance/`). It tests them together with the pricing pipeline, and it asks whether
a better design exists for each part.

**Why now:** these two systems are a headline of the product pitch to property management
companies. Mountain managers lose owners over missed turns, failed hot tubs, and lapsed
permits more than over rates. That is why ops and compliance are what this repo sells. But as
of 2026-10-05 they have only been checked by their own unit tests. **No market-sim board,
Guesty replay, forward shadow run, proving-ground world, or production-readiness audit has
exercised them.** This audit closes that gap. If the systems are weaker than the pitch
claims, say so plainly. A report that reads as a sales sheet has failed.

---

## 0. Ground truth and setup

### 0.1 Which code to audit

| Location | Status | Use it? |
|---|---|---|
| Branch `feature/ops-layer-wip` @ `56a2ffb` ("Harden operations layer for production"), on origin | Canonical, newest | **Yes** |
| Worktree `~/wp-price-worktrees/ops-layer` | Same branch, outside iCloud | Read-only reference |
| Main iCloud checkout (`.../Desktop/Harness for my wonderful Mother`) | Has **stale untracked copies** of `src/ops`, `src/compliance`, `config/operations`, `config/compliance`, `config/policies/operations.yaml`. These differ from `56a2ffb`. It is missing `src/compliance/cli.py` and `docs/rules/OPERATIONS.md`. | **No.** Do not audit or edit these. |

Setup:

```bash
git -C ~/wp-price-worktrees/ops-layer fetch origin
git -C ~/wp-price-worktrees/ops-layer worktree add ~/wp-price-worktrees/ops-audit -b audit/ops-compliance origin/feature/ops-layer-wip
cd ~/wp-price-worktrees/ops-audit
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
PYTHONPATH=. .venv/bin/python -m pytest -q --ignore-glob="* 2.py"
```

- Keep every worktree, run directory, and SQLite file **outside iCloud Drive**. iCloud duplicates
  and corrupts SQLite files and makes `* 2.py` copies.
- Run the CLI as `PYTHONPATH=. .venv/bin/python -m src.cli.main ...`. `uv run wp-price` fails
  with `ModuleNotFoundError: src`.
- Put large outputs in `~/wp-price-runs/ops_audit/`.

### 0.2 Read first, in order

1. `README.md`, `docs/LOCKED_INPUTS.md`, `docs/ARCHITECTURE.md`. These are operator decisions.
   Flag a problem with one. Do not override it.
2. `docs/rules/OPERATIONS.md`: the ops doctrine, including what ops may and may never do.
3. `docs/rules/AUTONOMY.md`: the autonomy ladder and hard invariants that ops must fit inside.
4. `config/policies/operations.yaml`, `config/operations/mont_luxe.yaml`, `config/compliance/*.yaml`,
   the `models` and `operations` blocks of `config/policies/default.yaml`.
5. `src/ops/**`, `src/compliance/**`, `src/receipt/owner_monthly.py`, and the readiness and
   min-stay paths in `src/compose/__init__.py` and `src/pricing/__init__.py`.
6. `tests/ops/**` (5 files, about 64 tests).
7. `docs/reports/MOUNTAIN_OPERATOR_RESEARCH_SAMPLE_2026-09-30.md`: what buyers say they need.
8. `docs/reports/PRODUCTION_READINESS_AUDIT_2026-09-20.md` and
   `docs/PRODUCTION_READINESS_AUDIT_PROMPT.md`: the house audit style. Match its rigor.
9. `docs/reports/market_sim/BASELINE_DIAGNOSIS.md`: the pricing engine currently loses to a
   flat rate in simulation. Any revenue effect of ops must be measured against that baseline.
10. `git log --oneline -30` on the audit branch.

### 0.3 Known facts. Verify them; don't rediscover them as findings.

- Every number in the ops profiles has `basis: estimate`. None are operator-confirmed.
- Jurisdiction is null for the two Northwoods homes. `management_fee_pct` is null.
- The compliance rule packs (Winter Park, Fraser, unincorporated Grand County) are
  **unreviewed** transcriptions.
- The Guesty Tasks, Breezeway, and Turno adapters were built from public docs. They have never
  been verified against a live account.
- `models.ops_aware_stay` is **off**. Its documented limit is that it assumes every candidate
  stay sells, so it can't see the demand a longer minimum stay loses.
- `operations.readiness_gate` is **on** but does nothing until an asset event is recorded.
- Ops-sourced minimum stays must never be pushed to Guesty.
- Private outputs go to `~/Library/Application Support/MontLuxePricing/{ops,receipts/owner}`.

### 0.4 Hard rules

- **No writes to Guesty.** No `--apply`, no `--confirm-live-write`, and no non-dry-run adapter.
- **Never open the operator database for writing.** Copy
  `~/Library/Application Support/wp-price/data/wp_pricing.db` into the run directory and work on
  the copy.
- Do not change `models.*.enabled` or `readiness_gate` in `config/policies/default.yaml`. Try
  policy variants as copies in the run directory, using `--engine-policy` where it applies.
- Do not change scoring, calibration, or existing worlds in `proving_ground_exam/market/`. New
  simulation code goes in new files (see Stage 4). Run `scripts/check_proving_ground_isolation.py`
  afterwards.
- Don't present a guess about a law, an ordinance, or an API as fact. Anything not confirmed
  from an official page you opened is marked `unverified`, with the URL you tried.
- Commit only to `audit/ops-compliance`. Don't merge or push without the operator's approval.

---

## 1. Inventory and contract map (one agent, deterministic first)

Before anyone forms an opinion, produce `01_inventory.md`:

1. **Entry points:** every CLI command under `ops` and `compliance`, with flags, what it reads,
   what it writes, and whether it can reach the network.
2. **Data:** every table in `src/ops/schema.sql` and the compliance tables. For each one, list
   who writes it, who reads it, and whether reads are point-in-time (filtered by `as_of` or
   `decision_date`).
3. **Config:** every key in `operations.yaml`, `config/operations/*.yaml`, and
   `config/compliance/*.yaml`. Mark which ones code actually reads. A key nothing reads is a
   finding.
4. **Consumers:** trace each ops or compliance output to where it ends up. That could be the
   compose readiness gate, min-stay resolution, the push path, explanations, owner receipts,
   the shadow report, or nowhere. Draw this as a table: output → consumer → effect on price,
   autonomy, or inventory.
5. **Tooling:** `pytest --cov=src/ops --cov=src/compliance --cov-branch`, `mypy`, and `ruff` on
   both packages. Give per-file coverage and list the uncovered branches that matter.

This map is the input to every later stage. Each stage agent reads it before starting.

---

## 2. Component correctness review

Run one sub-agent per group, each in its own worktree. Every agent follows the same loop:
**test → interrogate → research → improve → report → self-critique.** Each finding needs a
failing test or a command that reproduces it. A finding with neither is labeled `suspected`.

### 2A. Turns (`turns.py`)

- Owner stays, same-day turns, back-to-back stays, cancellations, modifications that move
  dates, overlapping or duplicate reservations, blocked nights, and multi-unit listings.
- Check-in and checkout times, `America/Denver` time zone, daylight-saving changes (the
  November 1 to 2, 2026 boundary), and dates stored as UTC.
- Is `turn_id = property|departing|arriving` stable when a reservation is modified? What
  happens to an existing turn when a booking fills a gap?
- Slack equals check-in minus checkout, minus work, travel, and the weather buffer. Check each
  term's units and sign. Check what happens when slack goes negative.

### 2B. Economics (`economics.py`)

- **Point-in-time:** no outcome, capacity snapshot, or signal recorded after `as_of` may affect
  a decision. Write a test that tries to leak future data and confirm it fails.
- Turn cost: the switch at 5 observed turns, outlier handling, and the basis and sample size
  reported with each number.
- P(ready on time): the Beta prior, the slack bucket edges, and behavior when a bucket has no
  data. Is the shrinkage sensible with fewer than 20 turns per home?
- Capacity: worker-minutes by zone and date. What happens with crew aliases, one cleaner
  covering two zones, and no capacity snapshot at all?

### 2C. Readiness state machine (`readiness.py`)

Use property-based tests (Hypothesis) that generate random event sequences, and assert these
invariants:

- Automated actors (signals, telemetry) can only move a property to `at_risk`, and never move
  it toward ready.
- `verified_ready` requires a named person, or a sensor reading that passes
  `readiness.sensor_verification`.
- An expired risk window never counts as recovery.
- Recovery closes events only for the system that has evidence. It refuses while another
  critical system still has an open event.
- Every transition cites an `asset_health_events` row.
- The current state is derived from the history and is identical however you query it.

Also check: invalid transitions, events for two systems at once, a sensor that flaps, a
clock-skewed sensor, and a property with no events (it must behave exactly as if ops did not
exist).

### 2D. Incidents and actions (`incidents.py`, `actions.py`)

- Idempotency: the same signal window must produce the same incident across reruns and partial
  reruns.
- Every name in `FORBIDDEN_ACTIONS` must raise `ForbiddenAction` in every code path, including
  CLI, batch approval, and rules in `operations.yaml`. A rule listing a forbidden action must
  fail the scan.
- Is the forbidden list complete for what a manager would consider high-liability? Examples:
  sending guest messages, sending access codes, refunds, cancellations, closing availability,
  paying vendors, and making safety determinations.
- Guest notice drafts: do the templates contain only verified facts, with no promises or
  admissions of fault?

### 2E. Sources and ingestion (`sources/*`, `normalize.py`, `webhooks.py`)

- Malformed CSV, duplicate rows, rows in the wrong time zone, unknown crew aliases, and an
  empty file.
- Webhooks: signature check, replay protection, ordering, and duplicate delivery.
- Guesty Tasks, Breezeway, and Turno: list every field each adapter assumes. Check each against
  current public API docs, and cite the URL. Mark each field `confirmed-in-docs`, `assumed`, or
  `contradicted`. Nobody has a live account yet, so build recorded fixtures from the docs.
- Telemetry: what happens with units, missing readings, and a sensor that reports a stale
  timestamp.

### 2F. Shadow report (`shadow.py`, `wp-price ops report`)

- Confirm it opens SQLite read-only and writes nothing. Check file modification times and the
  DB hash before and after.
- Historical runs: are the stored profile versions used, and is a missing version disclosed?
- Is the "extra turns per min-stay setting" worst case computed correctly?

### 2G. Compliance register (`src/compliance/`, `config/compliance/*`)

- Each check returns exactly one of: `evidence_on_file`, `unverified`, `expiring`, `expired`, or
  `missing`. No output, receipt, or CLI line may contain the word "compliant" as a verdict.
  Grep for it.
- Date math: warn windows, renewal dates versus expiry dates, leap years, and timezone.
- Each rule pack entry needs a source URL and a review state. **Open every source URL.** Record
  whether it loads, whether the rule text still matches, and the page's last-updated date.
  List any requirement the official page shows that the pack is missing.
- Jurisdiction resolution: what happens to the two Northwoods homes, whose jurisdiction is null?
  Silence is a finding. It must show up as `missing` or `unverified`, loudly.
- Look for cross-checks with data the repo already has. Examples: reservation `guest_count`
  against permitted occupancy, nights booked against any night cap, and whether the listing
  shows the permit number where required.

### 2H. Owner receipt (`src/receipt/owner_monthly.py`)

- Every ops or compliance statement shown to an owner must trace back to a row. No estimate
  may appear as observed data, and no "compliant" claim may appear.
- Owners must be kept separate: one owner's receipt must never show another owner's homes.

---

## 3. Integration with the rest of the system

This stage matters most. Ops and compliance are only as good as their effect on what the
pricing pipeline actually does. Build a matrix test, `tests/ops/test_integration_matrix.py`,
that runs `compose` end to end over:

- **Readiness state:** none, ready, at_risk, inspection_required, out_of_service,
  remediation_in_progress, verified_ready
- **Computed autonomy:** watch, suggest, handle, escalate
- **Night type:** peak blackout, normal peak, shoulder, orphan gap
- **Direction:** model wants up, down, or no change

For every cell, assert:

1. Ops only **restricts**. It never raises a price, never lowers a price because feasibility is
   low, and never grants autonomy.
2. `at_risk` and `inspection_required` demote `handle` to `suggest`. `inspection_required`
   blocks upward moves. `out_of_service` and `remediation_in_progress` block the night and
   *recommend* a closure without performing one.
3. The order is correct relative to guardrails, sanity bounds, and conservative rounding. A
   readiness shift must not let rounding or a move cap push the price past a limit.
4. The explanation lists the readiness reason with its dollar contribution, ranked correctly.
5. A property with no ops data produces **byte-identical** output to running with ops disabled.

Then test the seams:

- **Push path:** with the `dry_run` adapter, confirm that ops-sourced min-stays are dropped and
  that blocked nights never produce a rate or availability write. Inspect the adapter payloads.
- **Data-health gate:** stale ops feeds (tasks, telemetry, capacity) don't affect data health
  today. Should they? Show what happens when the task feed is 3 days stale and a turn is tight.
- **Guesty sync to turns:** run `sync-guesty` (read-only pull) and then `ops report` on the **copy** of the operator DB. Count
  turns, owner stays, and negative-slack turns. Cross-check a sample against the Guesty
  reservation records by hand.
- **Signals to weather buffer and incidents:** feed `signal_observations` with a real
  storm-day sequence. Confirm the weather buffer and incident window only use what was known
  by `as_of`.
- **Unscoped runs:** the 2026-09-20 audit found that unscoped `recommend` and `push` price every
  property in the database, including an undeclared Guesty listing (`creekside_haven`). Does any
  ops or compliance command have the same default? Each one must only touch homes declared in
  `config/portfolio/mont_luxe.yaml`.

---

## 4. Simulation: put ops into the proving ground

There is no simulated evidence for ops today. Build it in **new files only**, for example
`src/proving_ground/ops_scenarios.py` plus `tests/ops/test_ops_scenarios.py`, and wire it as an
optional layer on the market sim. Don't edit existing market scoring or calibration.

### 4.1 Scenarios

Each scenario injects asset events, crew capacity, task outcomes, and signals into a market-sim
season:

| Scenario | What happens |
|---|---|
| `saturday_cleaner_noshow` | Peak-season Saturday crew drops by half |
| `hot_tub_failure` | Critical system fails 2 days before a peak arrival; repair takes 1–4 days |
| `storm_road_closure` | Snowstorm plus access-road closure on a turn day |
| `sensor_false_positive` | Telemetry flags a failure that isn't real |
| `stale_task_feed` | Task source stops updating for 72 hours |
| `crew_double_booked` | One crew assigned to two zones on the same day |
| `permit_expires_midseason` | A permit expires in January |
| `owner_stay_turn` | Owner block followed by a same-day guest arrival |
| `back_to_back_holiday` | Christmas week with three back-to-back turns |

### 4.2 Measures

Pair each scenario with ops on and ops off on the same seeds (30 seeds, `normal` world plus
two held-out worlds). Measure:

- Rate or inventory changes on restricted nights. **Target: exactly 0.**
- Stays sold that the crew could not service: turns with negative slack after booking.
- False restrictions: nights restricted that didn't need to be, and their simulated revenue
  cost.
- Escalations raised versus escalations a person would actually need.
- With `ops_aware_stay` turned on **in a policy copy only**: the revenue difference against
  ops-off **and** against the flat baseline. Report whether its known limitation (assuming
  every stay sells) causes measurable demand loss.

All of this is simulated. Label it that way and never present it as realized revenue.

### 4.3 Replay

Run `wp-price ops report` over the Guesty history for 2026-04-29 to 2026-09-19 on the DB copy.
List the real turns that would have been flagged as tight or at risk. Report how many there
were and what actually happened, where task data exists. If no task data exists, say so.

### 4.4 Forward shadow

Propose a forward shadow log for ops, a sibling to `src/eval/shadow.py`. Each day it records
predicted P(ready on time) and turn cost. Later it records what actually happened, so the model
can be scored against reality. Implement it only if it fits within Stage 4. Otherwise, specify
the schema and the scoring.

---

## 5. Is there a better way?

Each component needs a **keep / change / replace** verdict, backed by evidence. One research
agent covers each question. Cite every page opened. Search snippets don't count as sources.

1. **What buyers use today.** Compare against Breezeway, Turno, Guesty Tasks, Operto, Hostaway,
   Track, and Streamline for operations. For compliance, compare against Granicus Host
   Compliance, Deckard, and Avalara MyLodgeTax. Also compare against how the operators in the
   2026-09-30 research sample describe their workflow. For each, list what it does that ours
   doesn't, what ours does that it doesn't, and whether we should integrate, match, or
   differentiate.
2. **The turn model.** Is turn plus slack plus Beta-shrunk P(ready) the right abstraction? Weigh
   it against scheduling or queueing approaches, plain rule-based checklists, and what turnover
   tools already compute. Favor the simplest design that is still honest at a 3-to-200-home
   scale.
3. **The ops-to-pricing bridge.** Weigh `ops_aware_stay` against alternatives: a gap-night or
   turn surcharge, a turn-day restriction such as no check-in on crew-short days, or closed-to-
   arrival rules. Use the Stage 4 numbers.
4. **The readiness states.** Are seven states too many for a property manager to operate? What
   would an operations lead actually update from a phone at 7 a.m.?
5. **Compliance scope.** For Colorado mountain markets, what does a manager actually get fined
   or delisted for? Examples: lodging and sales tax licenses, STR permits and caps, occupancy
   and parking limits, septic limits, smoke and CO detectors, hot tub rules, insurance minimums,
   and showing the license number on listings. Mark which ones the register covers. Label every
   rule `unverified` until it's checked against an official source. Flag anything that needs a
   lawyer as **operator / legal review**.
6. **Multi-tenant readiness.** What would break if a 50-home manager onboarded tomorrow?
   Consider profiles per home, jurisdiction packs per market, crew rosters, access controls,
   and keeping owners' data separate.
7. **What's missing.** Look for features buyers would expect that don't exist. Examples:
   inspection checklists with photo evidence, vendor SLAs, damage claims, linen and consumable
   inventory, and owner-facing readiness history. Rank them by buyer value against build cost.

---

## 6. Check every claim in the pitch

The pitch "Revenue Engine Pitch for Property Managers" (2026-10-05) makes these claims. Mark
each one `true`, `true with caveat`, or `false`, and cite the code or test that settles it.

1. Turns are the unit of work. Slack equals check-in minus checkout, minus work, travel, and a
   weather buffer.
2. At risk stops automatic price changes, so a person must approve.
3. Inspection required also blocks price increases.
4. Out of service blocks the night and recommends a closure, but never closes it.
5. Disruptions open incidents with affected arrivals, departures, and turns. A person approves
   each step. Forbidden high-liability actions fail in code.
6. The operations layer is read-only toward Guesty. Automatic signals can only lower readiness,
   and only a named person can mark a home ready.
7. Compliance checks return one of five states and never declare a property compliant.
8. The Guesty Tasks, Breezeway, and Turno connections are built from public docs.

Write any claim that fails into the report with the fix needed to make it true, or the
rewording needed to make it accurate.

---

## 7. Critic pass

A separate agent that has not seen the stage reports' reasoning reviews every finding and
every keep/change/replace verdict. It must:

- Re-run each reproduction. A finding that won't reproduce is downgraded or dropped.
- Challenge severity in both directions.
- Look for what the stages missed, especially at the boundaries between ops and compose, and
  between ops and push.
- Check that no simulated number is presented as realized revenue and that no unverified rule
  is presented as law.

The lead agent resolves disagreements and records them in the report. Disagreements are not
deleted.

---

## 8. Fixing

- Fix **P0 and P1 findings** on `audit/ops-compliance`. Each fix gets its own commit with a test
  that failed before the fix.
- Larger redesigns from Stage 5 are **proposals only**. Describe them, estimate the work, and
  leave them unbuilt.
- Keep the whole suite green, excluding `* 2.py`. Report the counts before and after.

Severity scale:

| Level | Meaning |
|---|---|
| P0 | Could write a wrong rate, availability, or reservation, or leak one owner's data to another, or mislead an owner about compliance |
| P1 | Wrong restriction or missed restriction on a real night; a point-in-time leak; a pitch claim that is false |
| P2 | Wrong number in a report, a missing disclosure, a config key nothing reads, a fragile adapter assumption |
| P3 | Clarity, naming, dead code |

---

## 9. Deliverables

Put these in `docs/reports/ops_compliance_audit_<YYYY-MM-DD>/` on the audit branch:

1. `REPORT.md`. Start with the verdict in three sentences: can a property manager rely on these
   systems today, and what has to change first. Then:
   - the findings table: id, severity, component, one-line summary, reproduction, status
   - the integration matrix result
   - the simulation results, labeled simulated
   - the keep/change/replace table with evidence
   - the pitch claim check
   - open questions for the operator
2. `01_inventory.md` from Stage 1.
3. `simulation/`: scoreboards and run configs (no databases).
4. `research/`: one file per Stage 5 question, each with its sources.
5. A short `FOR_THE_OWNER.md` in plain English: what works, what doesn't yet, and what the
   operator must confirm. Cover profiles, jurisdictions, compliance packs, and the adapters.

Stop and report if a hard rule would have to be broken to continue. Don't work around it.
