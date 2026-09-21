# Mont Luxe Collection — Production-Readiness Audit Protocol

**Purpose of this document:** this is a standing prompt/spec, not a one-off note. Feed it
verbatim (or via `Agent({ prompt: <this file> + task-specific header })`) to a fresh
session or subagent team whenever you want a full audit-and-hardening pass on this
repository before it takes over real pricing decisions for Mont Luxe Collection's three
properties (312 Northwoods, 300 Northwoods, Cloud 9 — Winter Park / Fraser, CO).

**Design rationale (why this structure, not one-agent-per-file):** this repo is a tightly
coupled linear pipeline, not a set of independent services — most of the bugs worth
finding live at the seams between stages (ceiling → bookprob → compose), not inside any
one 40-line file. A large fraction of `src/` is single-file modules, so spinning up a full
test/interrogate/research/improve loop per file wastes agent-hours re-deriving context and
defers the interesting cross-module bugs to a single end-of-run integration pass, where
they're most expensive to trace back. This protocol instead: (1) runs cheap deterministic
tooling first to tell agents where attention is actually needed, (2) groups work by
pipeline **stage** so the agents most likely to catch a contract mismatch are the ones
already looking at both sides of it, and (3) never lets a verdict ship on a single agent's
say-so — every stage report and every Architect verdict gets challenged by a separate
critic before it's accepted. Do not skip the interrogation, research, or critic steps to
save time — "does this part deserve to exist, and did anyone check the answer" is as much
the point of this pass as "does it run without crashing."

---

## 0. Ground truth before you start

Read these first, in order, so every downstream judgment is anchored to what the operator
actually decided, not to assumptions:

1. `README.md` — mission, locked v1 decisions, module layout table.
2. `docs/LOCKED_INPUTS.md` — operator-confirmed inputs (authoritative; do not relitigate
   these unless you find they are actively causing incorrect behavior — flag, don't override).
3. `docs/ARCHITECTURE.md` — locked architecture.
4. `docs/rules/*.md` — pricing doctrine, autonomy ladder (`AUTONOMY.md`), comp data rules
   (`COMP_DATA.md`).
5. `config/policies/*.yaml` and `config/portfolio/mont_luxe.yaml` — the actual operating
   parameters (floors, curves, elasticity, guardrails, events, ownership split).
6. Recent git log (`git log --oneline -30`) — what's changed recently and why, so you don't
   re-flag something that was just deliberately reworked.

The business context: Mont Luxe Collection is a small, real property-management operator
in Winter Park, Colorado — three luxury homes sleeping 16–18 guests across Fraser and
Winter Park proper. Guesty is system of record; Airbnb is a connected channel. This is
the operator's own original design, not adapted from any named competitor's product —
don't assume or go looking for external lineage that isn't in the docs. The objective is
RevPAN via `P × P(book|P)`, not ADR or occupancy in isolation. Autonomy to auto-push
prices is computed from measured data health every run, with a deliberate grace period
(consecutive-failure count, not a threshold change) before a failing gate actually demotes
`handle`→`suggest` — that grace period is a locked, intended design (2026-09-20 amendment
in `docs/LOCKED_INPUTS.md` / `docs/rules/AUTONOMY.md`), not itself a finding. Treat any
*other* weakening of the autonomy gate — a loosened threshold, an asymmetric grace period
on the way back up to `handle`, a bypass not documented in those two files — as a
severity-1 finding. History available to the pricing models was widened 2026-09-20 from a
6–12-month cap to a multi-year (~5 year) target. That window is reconciled in
`docs/rules/PRICING_DOCTRINE.md` §Ceiling and `src/ceiling/`: use prior years of the
*same* season (YoY calendar-aligned weekdays first), still never mix seasons. Treat a
reintroduction of cross-season whole-history fallback, or a silent discard of same-season
history older than one year, as a severity-1 finding. This is not a hypothetical SaaS
product with thousands of listings — every design choice should be judged against "does
this serve three real houses run by a real small operator," not "does this scale to a
much larger competitor's portfolio."

---

## 1. Pipeline shape

```
   STEP 0                STEP 1                    STEP 2              STEP 3
┌───────────┐   ┌──────────────────────┐   ┌───────────────────┐  ┌──────────────┐
│  STATIC   │   │    STAGE AGENTS       │   │  LIVE INTEGRATION  │  │  ARCHITECT   │
│ PRE-PASS  │──▶│  (parallel, ~5)       │──▶│  RUN (one agent,   │─▶│  SYNTHESIS   │
│ (no LLM)  │   │  each: test→interro-  │   │  full wp-price     │  │  + CRITIC    │
│           │   │  gate→research→       │   │  sequence, real    │  │  CHALLENGE   │
│           │   │  improve→report, plus │   │  cadence)          │  │              │
│           │   │  a CRITIC pass on     │   │                    │  │  → per-part  │
│           │   │  its own report       │   │                    │  │  verdict +   │
│           │   │  before it ships      │   │                    │  │  final       │
└───────────┘   └──────────────────────┘   └───────────────────┘  │  readiness    │
                                                                    │  verdict      │
                                                                    └──────────────┘
```

- **Step 0 — Static pre-pass.** No agent judgment yet, just deterministic tooling, run
  once. Its output is a triage map that tells every later agent where to actually spend
  interrogation/research effort instead of re-verifying what a tool already checked for
  free. See §2.
- **Step 1 — Stage Agents.** Not one agent per file — one agent per **pipeline stage**,
  each covering several related modules together (see §3 for the grouping). Because a
  stage agent holds both sides of an intra-stage handoff in its head at once, it catches
  contract mismatches that a single-file agent structurally cannot. Each stage agent's own
  report is reviewed by a **Critic** (§5) before it's allowed to reach the Architect —
  self-reported "looks fine" never ships unchallenged.
- **Step 2 — Live integration run.** One agent runs the entire `wp-price` sequence
  end-to-end, exactly as the operator's real cadence would, after all stage work has
  landed. This is unchanged in spirit from a big-bang integration test, but it now runs
  against a codebase that's already had its stage-level contracts checked, so what's left
  to find here is genuinely emergent, cross-stage behavior — not the leftovers of modules
  that were never looked at together.
- **Step 3 — Architect synthesis.** Never touches code directly. Reads every stage report
  (post-critic), the integration report, and issues one of three verdicts per part —
  **fix**, **improve**, **dismantle** (§6) — plus a whole-system research pass and a final
  production-readiness verdict. Every Architect verdict is itself challenged by the Critic
  before it's final (§5) — the Architect does not get a free pass any more than a Stage
  Agent does.

Use the `Agent` tool to run Step 1's stage agents in parallel (they're independent of each
other by construction — see the stage boundaries in §3), then Step 2 as a single sequential
agent once Step 1 has landed, then do Step 3 synthesis yourself as Architect, invoking the
Critic role as a distinct agent (or a distinct, adversarial pass if run in the same session)
before finalizing anything.

---

## 2. Step 0 — Static pre-pass (no agent judgment)

Run this once, before any agent starts interrogating or improving anything. It costs
nothing but compute and it tells every later step where the real risk is, so agent time
goes to interrogation and research — the things tooling can't do — rather than mechanically
re-running things a linter already covers.

Run and capture output for:

1. **Test coverage.** `pytest --cov=src --cov-report=term-missing` (or equivalent) across
   the full `tests/` suite. Flag every module with zero or thin coverage — that's where a
   Stage Agent's own new-test-writing effort (§3, Step 3) should concentrate.
2. **Static typing / contract check.** Run `mypy` (or `pyright`) across `src/` if configured;
   if not configured, that absence is itself a Step 0 finding worth flagging to the
   Architect — a rules-first pricing pipeline with untyped module boundaries is a real risk
   surface.
3. **Dead code / unreferenced symbols.** `vulture` or an equivalent unused-code scan across
   `src/`. Anything flagged here is a direct lead for the "interrogate ruthlessly" step —
   don't make a Stage Agent rediscover dead code by hand that a tool already found.
4. **Cross-module shape check.** Write (once, reusably) a small contract-assertion script
   that, for each stage boundary in §3, loads a representative sample of what the upstream
   module actually produces and asserts it matches what the downstream module's function
   signature / expected schema requires (field names, types, units — e.g. confirm
   `src/features` emits exactly the shape `src/ceiling` and `src/bookprob` consume). This
   is cheap, deterministic, and catches the single most common class of pipeline bug
   (silent schema drift) without needing an agent to trace it by hand.
5. **Dependency / config audit.** `pip check` for dependency conflicts; a quick script that
   loads every YAML in `config/policies/` and `config/portfolio/` and confirms they parse
   and don't contain internally contradictory values (e.g. a floor above a ceiling).

Produce one **triage map**: a short table of `module/stage → {coverage, contract-check
result, dead-code flags, config issues}`. Hand this to every Stage Agent as an input — it
is not optional context, it is the map that tells the agent what to spend its limited
interrogation and research budget on, rather than starting from zero on every module
regardless of known risk.

---

## 3. Step 1 — Stage Agents

### Stage grouping (replaces the old one-agent-per-file list)

| Stage | Modules covered | Why grouped together |
|---|---|---|
| **A — Acquisition** | `src/ingest/`, `src/pms/`, `src/scrape/`, `src/signals/` (collectors + extractors) | Everything that pulls data in from the outside world (Guesty, CSV/iCal, market sweeps, external signal sources). The shared risk is silent upstream failure — a rate-limited API, a changed page structure, a stale feed — and whether that failure is detected and reflected in data health rather than passed downstream as if it were good data. |
| **B — Signal processing & scoring** | `src/signals/` (features, orchestrator, promotion, store, comp_movement), `src/comps/`, `src/resort/` | Turns raw acquired data into scored, curated evidence (comp freshness/coverage, signal ladder, resort ops features). The shared risk is a scoring/promotion rule that's individually reasonable but produces a signal set the pricing stage can't actually use, or double-counts something Stage A already flagged as low-confidence. |
| **C — Pricing decision** | `src/ceiling/`, `src/bookprob/`, `src/leakage/`, `src/elasticity/`, `src/compose/` | The actual `P × P(book\|P)` optimization core. Grouped together because these five modules are the tightest-coupled part of the whole repo — a unit mismatch or a silently-wrong assumption in `bookprob` only shows up as a wrong number three modules later in `compose`, so one agent needs to trace the number through all five to catch it. **Locked ceiling doctrine:** history is multi-year (~5 years) and same-season; year-over-year calendar-aligned weekdays are preferred; cross-season fallback stays forbidden. Verify `docs/LOCKED_INPUTS.md`, `docs/rules/PRICING_DOCTRINE.md` §Ceiling, and `src/ceiling/` still agree. A drift back to whole-history pooling or to discarding prior years of this season is a finding. |
| **D — Safety & explainability** | `src/guardrails/`, `src/explain/`, `src/audit/` | The layer that decides whether Stage C's output is allowed to reach a real listing, and whether a human can understand why. Kept separate from Stage C deliberately — this agent's job is partly adversarial toward Stage C's output by design (does the guardrail actually catch what Stage C could get wrong?), which pairs naturally with the Critic role in §5. **Known open item:** `docs/rules/AUTONOMY.md` locks in a grace period (N consecutive failing health checks, not a threshold change) before a failing gate demotes `handle`→`suggest`; `assess_data_health()` does not implement this yet. Building it — asymmetric on purpose, no equivalent grace period re-arming `handle` — is in-scope work for this stage, and every other hard invariant in `AUTONOMY.md` must remain untouched by the change. |
| **E — Output, ops & governance** | `src/eval/`, `src/db/`, `src/cli/`, `config/policies/*.yaml`, `config/portfolio/mont_luxe.yaml`, `scripts/*.sh` | The operator-facing and infrastructure layer: reporting, schema, the `wp-price` CLI surface, governed policy files, and the cron/launchd jobs that run unattended. Grouped together because these are all "does the human actually get correct, trustworthy visibility and control," as opposed to the pricing math itself. |

If the repo has grown a directory that doesn't fit one of these five stages, add a stage
rather than forcing a bad fit — the boundary should track real coupling, not this table.

### Per-stage agent loop

Each Stage Agent receives: this document, the Step 0 triage map, and its stage's module
list. It runs:

1. **Test — informed by the triage map, not from zero.** For each module in the stage,
   run/extend tests, prioritizing what Step 0 flagged as thin coverage or a contract-check
   failure. Additionally, and this is the part single-module agents structurally can't do:
   trace at least one realistic value **across the stage's internal handoffs** — e.g. for
   Stage C, pick one property/date, and manually verify the ceiling value, the booking
   probability, the leakage adjustment, and the elasticity override are all consistent
   units and actually feed `compose` correctly, not just that each module passes its own
   tests in isolation.
2. **Interrogate ruthlessly — per module and per stage.** For each module: why does it
   exist, what does it cost to keep, does it match locked doctrine (cite the specific
   doc/section), is it a relic of a superseded decision. For the stage as a whole,
   additionally ask: is this grouping of modules actually doing one coherent job, or does
   the stage contain a module that doesn't belong and creates a hidden coupling? Do not
   soften findings — the Critic and Architect need the unfiltered version.
3. **Research — module-level and stage-level.** For each module's specific sub-problem,
   and for the stage's job as a whole, check how established players solve it: **Guesty**
   (native baseline this repo must justify departing from), **PriceLabs**, **Beyond
   Pricing**, **Wheelhouse**, **AirDNA/Key Data**, and **Vantry.ai** if verifiable — do not
   fabricate detail about a tool you can't confirm; say so if you can't find it. Judge
   "better" against a 3-property owned-code operation, not against SaaS-scale
   sophistication.
4. **Improve.** Implement fixes/improvements within the stage's own blast radius. A
   cross-stage interface change (e.g. changing what Stage B hands to Stage C) must be
   flagged to the Architect, not made unilaterally — no single Stage Agent sees every
   consumer of a cross-stage boundary.
5. **Report**, using the template in §7.

### Critic pass on each Stage Agent's report (this is new — do not skip)

Before a Stage Agent's report is considered final, a separate **Critic** pass runs against
it — either a distinct Agent invocation given only the stage's report and a copy of the
actual diff (not the stage agent's summary of the diff), or, at minimum, a distinct
adversarial pass within the same session that does not reuse the stage agent's own framing.
The Critic's job:

- Spot-check at least one "pass" and one "fix (done)" claim against the actual code/tests,
  not the report's prose — confirm the fix is real and the test that would have caught the
  original bug actually exists and actually fails on the pre-fix code.
- Challenge every "why this exists" interrogation answer that reads like a rationalization
  rather than a verified reason — if the stage agent's justification for keeping a module
  is vague, push back and ask it to find the concrete decision or usage that justifies it.
- Challenge any research claim that isn't backed by a checkable citation or an honest
  "couldn't verify."
- Flag anything the stage agent recommended as **dismantle** without confirming no
  downstream stage depends on it — this is the highest-cost mistake a stage agent can make,
  since it can't see other stages' consumers.

The Critic does not have to be exhaustive on every line — it should behave like a skeptical
senior reviewer sampling for the failure modes above, the same spirit as this repo's own
`/code-review` critique pass. A report that fails Critic review goes back to the Stage
Agent with specific objections, not to the Architect.

---

## 4. Step 2 — Live integration run

After all Stage Agents' reports have passed Critic review, run the **entire program as one
system**, exactly as the operator's real daily/seasonal cadence would, using the sequence
in the README quick start and `scripts/daily_scrape.sh` / `scripts/dec2023_replay.sh`:

1. `init-db` → `seed-sample` (or `sync-guesty` against real/sandboxed credentials if safe
   and available; do not touch production Guesty rate-push endpoints without explicit
   human confirmation).
2. `discover-comps` → `scrape-comps`.
3. `snapshot` — including deliberately testing what happens if this step is skipped for
   one or more days, since the README calls a skipped day "permanently unrecoverable."
4. `health` — confirm the autonomy gate computes correctly from the data health state
   actually produced in steps 1–3, not from a hand-set flag.
5. `signals cycle` / `signals scoreboard` / `signals promote`.
6. `recommend` — confirm recommendations carry booking probability and expected RevPAN.
7. `push --adapter dry_run` — confirm it refuses when health doesn't grant `handle`, and
   only proceeds within guardrails when it does.
8. `report` and `audit`.

Report on:
- **Emergent cross-stage failures** — things that only break when stages chain (a shape
  mismatch the Step 0 contract check didn't cover because it only checked one stage
  boundary, a race between snapshot timing and ingest, a guardrail correct alone but
  bypassed by a specific sequencing).
- **End-to-end doctrine correctness** — trace one concrete recommendation for one
  property/date all the way from raw signal to final price and confirm every number in the
  chain is real, not a stub or hardcoded default masking a broken upstream step.
- **Operational realism** — what happens when this runs unattended via launchd at 07:00 and
  something upstream is down or rate-limiting: fail loud, fail safe (demote autonomy), or
  fail silent?
- **Three-property specifics** — confirm the owner-scoped separation (312+300 Northwoods vs.
  Cloud 9) stays reporting-only and never leaks into pricing.

File this using the same template shape in §7, scoped to "whole system." This report also
goes through a Critic pass before reaching the Architect, for the same reasons as §3.

---

## 5. The Critic role (cross-cutting, not a one-time step)

The Critic is not a phase that runs once at the end — it's a role invoked twice: after
every Stage Agent report (§3) and after the Architect's synthesis (§6), so no verdict in
this whole protocol ships purely on the say-so of the agent that produced it. Concretely:

- The Critic should be run with **as little of the producing agent's own framing as
  possible** — give it the underlying evidence (diffs, test output, the actual research
  citation) rather than just the producing agent's prose summary, so it isn't just
  re-reading and agreeing with a narrative.
- The Critic is explicitly allowed, and expected, to send a report or verdict back for
  rework rather than rubber-stamping it with minor caveats.
- The Critic's own output is not itself re-audited — at some point this has to terminate —
  but the Critic should flag its own confidence level per challenge so the Architect (or,
  for the final Architect verdict, the human operator) knows which challenges were
  thoroughly checked versus spot-checked.

---

## 6. Step 3 — Architect synthesis (with Critic challenge)

Once you (Architect) have every Stage report (post-critic) and the integration report
(post-critic):

1. **Build the cross-stage reference.** For each stage boundary (A→B, B→C, C→D, C/D→E),
   check the upstream stage's actual output against the downstream stage's actual
   consumption, using the Step 0 contract checks plus anything the integration run
   surfaced. Flag any place a Stage Agent said "fine" but the integration run or the
   contract check contradicts it.
2. **Issue a verdict per module** (not just per stage — the stage grouping is for agent
   efficiency, the verdict granularity stays at the module level), one of:
   - **Fix** — correct, keep as-is.
   - **Improve** — keep the concept, change the implementation; state what and why,
     informed by both stage-level and whole-system research.
   - **Dismantle** — doesn't justify its cost; state the replacement (if any) and confirm,
     via the Step 0 contract map, that nothing downstream silently depends on it.
   Do not default to "fix" out of inertia.
3. **Whole-system research pass.** Compare the end-to-end approach (rules-first RevPAN
   optimization, computed autonomy ladder) against how Guesty's native tools, PriceLabs,
   Beyond Pricing, Wheelhouse, and (if verifiable) Vantry.ai approach the whole problem for
   small luxury portfolios. Look for gaps invisible at the stage level: a capability
   category competitors have that no stage covers at all, redundant capability spread
   across stages that could consolidate, or an architecture choice fighting the grain of
   how this class of tool is normally built.
4. **Submit your own synthesis to the Critic before finalizing.** Same rules as §5: give
   the Critic the underlying stage reports and integration report, not just your summary of
   them, and expect pushback on any verdict that isn't well-supported.
5. **Production-readiness verdict**, post-critic. State plainly whether this repo is ready
   for Mont Luxe Collection to run in production for real pricing decisions across all
   three properties. If not, a prioritized, concrete punch list — weighted by real
   consequence (a bug that could push a wrong price live or corrupt pacing history outranks
   a style nit by a wide margin).

---

## 7. Report template (Stage Agent → Critic → Architect; Integration Agent uses the same shape)

```
STAGE: <A–E, or "integration">
MODULES COVERED: <list>
STATUS: pass | fail | pass-with-findings

TRIAGE MAP INPUTS USED: <what Step 0 flagged for this stage, and how it shaped effort>

WHAT THIS STAGE DOES (in your own words, after reading the code): ...

TEST RESULTS (per module, plus at least one traced cross-module value): ...

INTERROGATION FINDINGS (per module, plus "does this grouping cohere as one stage"): ...

RESEARCH (per module and for the stage's job as a whole, with source/confidence): ...

CHANGES MADE: <diff summary, files touched, tests added>

RECOMMENDATION PER MODULE: fix (done) | improve (specify) | dismantle (specify replacement
or confirm none needed) — one sentence of justification each.

CROSS-STAGE FLAGS FOR THE ARCHITECT: <anything needing context this agent doesn't have>

--- CRITIC REVIEW ---
SPOT-CHECKS PERFORMED: ...
CHALLENGES RAISED: ...
RESOLUTION: accepted as-is | sent back for rework (with specifics) | accepted with noted
residual concern for the Architect
```

---

## 8. Ground rules for whoever executes this protocol

- This is real production software for a real small business. Treat data loss, a wrong
  price pushed to Guesty/Airbnb, or a weakened autonomy gate as the highest-severity class
  of finding there is — higher than any code-quality issue.
- Never run `push` against a live, non-`dry_run` adapter, and never call `sync-guesty` in a
  way that could write back to the real Guesty account, without explicit human confirmation
  first — this protocol authorizes testing and improving the code, not transacting against
  the operator's live systems.
- Prefer the smallest correct fix over a rewrite. This repo's own values (rules-first,
  owned code, markdown-governed policy, sized for three houses, not a SaaS competitor)
  should shape every "improve" recommendation.
- Cite research honestly. If you can't verify a competitor detail or technique, say so
  instead of presenting a guess as fact.
- Keep git discipline throughout: commit logically, don't bundle unrelated fixes into one
  commit, and never force-push or discard uncommitted work without checking `git status`
  first.
- Produce a final, human-readable summary for the operator (Jacob) at the end: current
  production-readiness verdict, what was fixed, what was dismantled and why, what's still
  open, and the prioritized punch list from §6.5.
