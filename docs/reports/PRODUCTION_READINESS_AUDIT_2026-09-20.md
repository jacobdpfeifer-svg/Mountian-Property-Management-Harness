# Mont Luxe Collection production-readiness audit — 2026-09-20 (re-run)

Full re-run of the protocol in `docs/PRODUCTION_READINESS_AUDIT_PROMPT.md`: Step 0
static pre-pass → five parallel Stage Agents (A–E), each running test→interrogate→
research→improve→report→self-critic in an isolated git worktree → merge → Step 2 live
integration run → this Architect synthesis, itself challenged by a Critic pass before
being finalized. Superseded the previous same-day run
(`docs/reports/PRODUCTION_READINESS_AUDIT_2026-09-20.prior-run.md`), whose open items are
re-verified below rather than assumed closed.

## Architect verdict

**Still not ready for unattended `handle`-level auto-push.** The pricing core is in
materially better shape than the prior run — the multi-year ceiling doctrine gap is now
genuinely closed and independently re-verified, deterministic tooling is installed and
was used throughout, mypy errors fell from 51 to 2, coverage rose from 70% to 80%, and a
real, previously-missing hard invariant (a symmetric high-side sanity ceiling against
corrupted PMS input) was found and fixed. But this run's live integration pass surfaced
one new finding serious enough to move it above every carry-over item on the punch list:

**`wp-price recommend` / `wp-price push` default to pricing every property row in the
database when no `--property`/`--owner` flag is given — exactly how the README's own
Quick Start invokes them — and a real, unconfirmed fourth Guesty listing
(`creekside_haven`, `owner_id=NULL`, never declared in `config/portfolio/mont_luxe.yaml`)
is present in the live tenant today.** Nothing currently stops that listing from
receiving real recommendations, and — the first time this system's write path is ever
exercised — a real price push, the moment health ever reaches `handle` without an
operator remembering to scope the run by hand. This is a structural default, not a data
corruption edge case; it does not require anything to go wrong to fire. Do not enable a
non-dry-run adapter, and do not run `recommend`/`push` unscoped against the real tenant,
until this is resolved — either by explicit operator confirmation of what `creekside_haven`
is, or by making `config/portfolio/mont_luxe.yaml`'s three properties the default scope.

Second-highest: `round_price_conservative` can round a composed price past its own
computed ceiling. It always rounds in a single direction per branch — floor or ceil,
never nearest — so the worst case approaches a full `round_to` (**≈$5 today**, not the
`round_to/2` this report originally claimed; corrected after the Critic pass below caught
the arithmetic error by reproducing it directly:
`round_price_conservative(691.0, 900.0, round_to=5) == 695.0`, a $4 overrun on a $691
ceiling). Real, found only because this run actually chained `recommend` output into
`audit` end-to-end — no single stage's own tests did that. Dollar impact is real but
still bounded (a few dollars per night, not a runaway price), and `wp-price audit` — the
tool meant to be the independent trust check — currently fails on ~48% of ordinary runs
because of it, which trains an operator to ignore its alerts. Fix before relying on
`audit` as a signal.

Third: the Guesty write path (`GuestyClient.set_rate`) has still never been fired at the
live tenant, appropriately — that remains a separately authorized human decision, not an
engineering blocker.

## Step 0 — deterministic pre-pass (re-run against current code)

| Check | Result |
|---|---|
| Tests | **134 passed** pre-merge → **213 passed** post-merge (+79 new tests across all 5 stages), 0 failed |
| Coverage | 70% → **80%** total; `signals/orchestrator.py` 0%→89%, `signals/analyst.py` 0%→82%, `eval/export.py` 0%→100%, `scrape/properties.py` 23%→90%, `pms/sync.py` 35%→84%, `weather.py` 19%→99%, `bookprob` 75%→80%, `promotion.py` 57%→90%, `comp_movement.py` 46%→96% |
| Typing | mypy: **51 errors → 2** (one unfixable third-party stub gap in `pyairbnb`; one traced-safe `Collector` kwarg typing note in `src/cli/main.py:626`, real fix lives in `src/signals/collector.py`'s `get_collector` typing, not urgent) |
| Dead code | vulture (60% confidence) surfaced mostly false positives (plugin-registered collector classes); genuine dead code confirmed by grep and removed or flagged: `guardrails.LEVELS`/`_rank` (removed), `eval/backtest.run_backtest` (flagged, not removed — file also holds live signal-scoring code), `signals/analyst.narrate_anomaly` (flagged), `signals/comp_movement.market_median_lift` (flagged, also measurably buggy) |
| Compilation | Pass |
| Contract/config preflight | Pass (`scripts/production_preflight.py`), both pre- and post-merge |
| Dependency audit | Pass — `pip-audit`: no known vulnerabilities |

## Per-stage summary

### Stage A — Acquisition (`src/ingest`, `src/pms`, `src/scrape`, signal collectors/extractors)

Pass-with-findings. Closed the stage's three largest coverage gaps (`pms/sync.py`,
`scrape/properties.py`, `weather.py`) and fixed every triage-flagged mypy error,
including a real type-contract bug in `signals/collectors/resort.py` (a constructor
declared a zero-arg callback but the code always called it with one argument — never
manifested against the shipped default, but would break any future caller that honored
the declared interface). Confirmed the Guesty write path remains reachable only through
the guardrail-gated `push_recommendations` call site. Flagged, did not resolve: whether
`push_recommendations`'s inline guardrail re-check duplicates `src/guardrails.apply_guardrails`
by design or by drift (Architect verdict below).

### Stage B — Signal processing & scoring (`src/signals/{features,orchestrator,promotion,store,comp_movement,analyst,collector,validate}`, `src/comps`, `src/resort`)

Pass-with-findings. Found and fixed two real robustness bugs in `orchestrator.py`: a
misconfigured collector's constructor error could crash the *entire* daily signal cycle
instead of just that collector, and passing `schedule=[]` was silently promoted to the
full default schedule (Python empty-list falsiness) — verified this actually fires live,
unwanted network calls. Confirmed the SQI kill switch and leak-free `as_of` read
discipline are real, not decorative. Found, did not fix (needs cross-stage coordination):
`Observation.observed_at` is silently truncated to a bare date before storage, which
defeats the CDOT access-risk signal's hourly staleness cadence within a single calendar
day — every `as_of` consumer across Stages C/D would need auditing before restoring
precision. Also found: the documented `active_to_deprecated.break_on_source_failure`
promotion-ladder policy is unimplemented (`demote_on_source_break` has zero callers).

### Stage C — Pricing decision (`src/ceiling`, `src/bookprob`, `src/leakage`, `src/elasticity`, `src/compose`)

Pass-with-findings, the stage's central open question resolved. **Independently
re-verified** (not accepted on the commit message's word) that commit `c648217`'s
multi-year same-season ceiling doctrine is genuinely implemented: reproduced the
pre-fix module from git history, confirmed the new regression tests fail to even
*collect* against it, and manually traced a same-season YoY→season×DOW→season cascade
live. Fixed the triage-flagged mypy cluster in `ceiling`/`compose`, resolving each one to
a concrete, traced answer rather than a blanket type-ignore. Found, flagged rather than
fixed unilaterally: `src/bookprob` does not apply the same 5-year `history_lookback_years`
cap that `src/ceiling` now does — not unsafe (still season-filtered, cross-property
pooled) but inconsistent with the letter of the multi-year lock; needs an explicit
Architect/operator decision on whether bookprob should share ceiling's cap.

### Stage D — Safety & explainability (`src/guardrails`, `src/explain`, `src/audit`)

Pass-with-findings, and this stage's own finding is the most consequential thing any
single stage agent found on its own: `apply_guardrails` had **no upper-bound sanity
check symmetric to its existing floor check**. Built a live trace — a corrupted
`listed_price` of $50,000 against a ~$690-anchor property — and confirmed the pre-fix
code would have clamped toward ~$49,750 and reported it as a safe `clamped_decrease`.
Fixed: added `sanity_max_ratio_to_anchor` (default 3.0, config-tunable) as a new hard
invariant, with `peak_blackout` correctly retaining label priority when both conditions
apply on the same night. Verified the amended grace-period doctrine (asymmetric,
fail-closed for a new scope, no threshold loosened) is genuinely implemented, not just
documented. Completed the previously-partial pacing-gap health check (an unscoped
count-only check could not distinguish "14 days of history" from "14 days with a hole in
the middle" — now it can). Flagged: `sanity_max_ratio_to_anchor: 3.0` was chosen
conservatively but not validated against a real high-demand week's actual Mont Luxe
pricing; the pacing-gap check's "since first sync ever" window has real operational bite
(a portfolio with any historical gap stays demoted until the operator backfills or the
gap ages out) and may want a bounded lookback instead.

### Stage E — Output, ops & governance (`src/eval`, `src/db`, `src/cli`, policy YAML, scripts)

Pass-with-findings. Chased the Step 0 mypy cluster in `src/eval/retrospective.py`
(~15 "attribute doesn't exist" errors) to ground: a shadowed loop variable name silenced
mypy across the whole function. Confirmed via reconstruction that it was never a live
`AttributeError` — Python's per-loop rebinding happened to save it at runtime — but it
was exactly the kind of bug-shaped mypy noise that would hide a real future field-name
typo in the operator-facing retrospective report. Fixed (pure rename), added a regression
test that mypy-checks the function directly. Closed `eval/export.py`'s 0%-coverage gap
(confirmed it is reachable via `wp-price export`, not dead). Identified that
`eval/backtest.py` is two things wearing one filename — `run_backtest` is genuinely dead,
but `score_signal_against_outcomes` in the same file is live, load-bearing signal-scoring
infrastructure Stage B's `promotion.py` depends on — recommended a rename/split rather
than a blanket dismantle.

### Integration (Step 2) — whole system, live-Guesty-informed

Pass-with-findings, and the source of this report's two highest-priority items:

1. **`round_price_conservative` can round past the computed ceiling** (Architect
   verdict: **fix**, S1). Root cause: it rounds toward `listed_price` as the anchor, not
   toward whichever bound (`floor`/`ceiling`) actually produced the pre-rounding value,
   so a value already clamped to the ceiling one step earlier in `compose` can round
   further away from `listed_price` and past that ceiling. It always rounds in a single
   direction (floor or ceil, never nearest), so the worst case approaches a full
   `round_to` (**≈$5 at the default setting**, not `round_to/2` — corrected by the Critic
   pass, which reproduced `round_price_conservative(691.0, 900.0, round_to=5) == 695.0`
   directly). No test in the whole suite exercised `round_price_conservative` directly,
   and Stage C never fed its own output through Stage E's `audit`, which is precisely how
   this went undetected until two stages were chained. Reproduced live: 104/216 (48%) of
   a real `recommend` run's rows failed `audit`'s `price_bounds` check.
2. **Unscoped `recommend`/`push` defaults to the full `properties` table**
   (Architect verdict: **fix**, S1, highest priority on this report — see verdict
   above). Independently re-verified this run (not cited from the prior session alone):
   a fresh read-only Guesty sync against a disposable DB copy reproduced the same 4
   listings, 81 reservations, 467 priced booked nights as the prior session, and — new
   this run — confirmed the 4th listing (`creekside_haven`) generates real, fully-formed
   recommendations when priced, gated only by today's incidental `suggest`-level health,
   not by any code path tied to `config/portfolio/mont_luxe.yaml`'s three-property list.
3. Confirmed operationally: `snapshot` failure is a genuine, permanent, irrecoverable
   data loss for that day (reproduced live via a real wall-clock midnight rollover during
   this run); `push` fails safe in every path exercised; `signals cycle` fails safe
   per-collector but has no run-level deadline (operational risk for a tightly-scheduled
   `launchd` job, not a correctness bug).
4. Confirmed: owner-scoping (`owner_id`) never reaches `src/ceiling`, `src/bookprob`,
   `src/leakage`, `src/elasticity`, or `src/compose` (zero matches across those five
   directories) — ownership separation stays reporting-only as designed. The one crack
   adjacent to this is finding #2 above: a property with **no** owner assignment
   (`creekside_haven`) is still fully priceable by the default path.

## Research synthesis (carried forward, re-confirmed, extended)

Unchanged from the prior run's conclusion and reconfirmed by every stage this pass: the
design is directionally aligned with Guesty (orchestration + third-party pricing tools,
not a native competitor), PriceLabs (seasonal min/base/max, market-wide comp dashboards —
this repo independently arrived at the same market-sweep-then-filter shape), Beyond
Pricing (gap-fill/orphan-night handling, comp clustering — this repo substitutes
rules-based filtering for Beyond's human-analyst review pass, a reasonable trade at
3-property scale), Wheelhouse (elasticity-based pricing, pacing-based dynamic
adjustment), and AirDNA (market-percentile-over-property-level reliability guidance,
which validates this repo's own `market_percentile` fallback design). New this pass: none
of the four verifiable competitors document anything resembling this repo's explicit
experimental→shadow→active signal-promotion ladder with per-signal information-coefficient
gating — a genuine point of differentiation, and the kind of rules-first discipline a
3-property owner-operator can maintain by hand that a black-box SaaS competitor has no
reason to expose. Vantry/Vantory lineage was again not used as a design assumption, and
this remains correct per the operator's own documentation.

## Per-module Architect verdict

| Module/group | Verdict | Rationale |
|---|---|---|
| Guesty adapter (`src/pms/guesty.py`) | **Fix (done)** | Correct, doctrine-matching, mypy-clean; write path stays correctly unexercised. |
| PMS sync (`src/pms/sync.py`) | **Fix (done)** | Coverage/mypy gaps closed; realised-price unit handling verified by trace. |
| `src/pms/__init__.py` (`push_recommendations`) | **Improve** | Inline guardrail re-check may duplicate `src/guardrails.apply_guardrails`; needs a joint read to determine deliberate defense-in-depth vs. drift risk. |
| `src/pms/webhooks.py` | **Improve** | Design is correct (never mutates price); `record_delivery`'s caller graph outside Stage A's files is still unconfirmed. |
| Scraper (`src/scrape/*`) | **Fix (done)** | Market-sweep design is sound; `scrape/properties.py` coverage gap closed. |
| `src/ingest/` (CSV/iCal) | **Improve** | Fine for demo/onboarding; its docstring's "so a PMS API can plug in later" rationale is stale since Guesty sync didn't adopt this interface — retire the claim, not the code. |
| Signal collectors/extractors | **Fix (done)** | Honest-degradation pattern holds throughout; real type bug in `resort.py` fixed; coverage gaps closed. |
| Signal orchestrator/promotion/store | **Fix (done)**, with **one Improve carried forward** | Two real robustness bugs fixed and regression-tested; `observed_at` date-truncation and the dead `break_on_source_failure` policy both need cross-stage/operator decisions before fixing. |
| `comps/`, `resort/` | **Fix (done)** | No defects found; honest usability/coverage discipline confirmed. |
| Ceiling (`src/ceiling`) | **Fix (done)** | Multi-year doctrine gap independently re-verified closed; mypy cluster resolved to traced, concrete answers. |
| Bookprob/elasticity | **Improve** | Correct and well-tested; bookprob's missing history-lookback cap is a real, low-urgency inconsistency needing an explicit doctrine decision. |
| Leakage | **Fix (done)** | Matches doctrine exactly. |
| Compose | **Fix (S1 item found this pass)** | Two low-severity bugs fixed by Stage C (stray `sqi_confidence`, wrong `lastrowid` on upsert); the ceiling-overrun rounding bug found by integration is a new, higher-priority fix (see verdict above). |
| Guardrails (`apply_guardrails`, `assess_data_health`) | **Fix (done)** | Real hard-invariant gap (no high-side sanity check) found and closed with a live corrupted-input trace; grace period and pacing-gap check both verified correct on live-reproduced scenarios. |
| Explain/audit | **Fix (done)**, `audit` **currently noisy** | Both modules are correctly designed (independent reimplementation in `audit`, dollar-ranked attribution in `explain`); `audit`'s real, correct `price_bounds` check will keep failing ~48% of runs until the rounding bug above is fixed — not a defect in `audit` itself. |
| Eval (`retrospective`, `export`, `backtest`) | **Fix (done)** for retrospective/export; **Improve** for backtest | Retrospective type-hygiene bug fixed and regression-tested; export coverage closed; `backtest.py`'s dead `run_backtest` should be split out from its live `score_signal_against_outcomes`. |
| `src/db/`, `src/cli/main.py` | **Fix (done)**, with **one S1 item found this pass** | Idempotent DB backfill confirmed correct; CLI surface is coherent; the unscoped `recommend`/`push` default is the highest-priority fix on this report (see verdict above), and lives here, in `_resolve_scope`/`resolve_property_ids`. |
| `config/policies/*.yaml`, `config/portfolio/mont_luxe.yaml` | **Fix (done)** | Coherent, well-documented; placeholder owner names are confirmed operator-intentional, not a defect. |
| Hostaway adapter | **Dismantle not recommended** (unchanged) | Inert interface seam; no production blast radius, must remain clearly non-operational. |

## Prioritized punch list

1. **S1 — NEW. Scope `recommend`/`push` to `config/portfolio/mont_luxe.yaml`'s declared
   properties by default**, or refuse to run unscoped against a non-demo, Guesty-synced
   DB without an explicit `--property`/`--owner`/`--all` flag. Resolve what
   `creekside_haven` actually is before it can receive any recommendation, real or
   dry-run. Highest-priority item on this report — the only finding that requires no
   data corruption or operator error to fire, only the README's own documented usage.
2. **S1 — NEW. Fix `round_price_conservative` to respect the ceiling/floor bound that
   produced its input**, not just round toward `listed_price`. Restores `wp-price audit`
   as a trustworthy signal (currently fails ~48% of ordinary runs for this reason alone).
3. **S1 — carried forward, still open.** Complete a separately authorized Guesty write
   canary: one property/date, read-back verification, dry-run comparison, rollback/abort
   procedure, operator approval. Two independent read-only Guesty syncs this pass
   confirmed the live tenant shape (4 listings, 81 reservations, 467 priced booked
   nights) but the write endpoint remains, correctly, untouched.
4. **S1 — carried forward, partially addressed.** Establish real three-property health
   history. A live `health` run this pass correctly demoted to `suggest` on 51 real
   pacing-continuity gaps since 2026-09-01 — the gate works, but real clean history still
   needs to accumulate (or the operator needs to decide whether "since first sync ever" is
   the right lookback for the new pacing-gap check vs. a bounded window).
5. **S1 — carried forward, now closed.** ~~Resolve and test the multi-year ceiling
   doctrine.~~ Independently re-verified closed this pass (pre-fix regression test,
   manual trace).
6. **S1 — carried forward, now closed.** ~~Install and run coverage, typing, dead-code,
   dependency tooling.~~ Done; used throughout this run (mypy 51→2, coverage 70%→80%).
7. **S2 — Decide whether `src/bookprob` should share `src/ceiling`'s 5-year
   `history_lookback_years` cap**, for consistency with the letter of the multi-year lock
   (not unsafe today, just inconsistent).
8. **S2 — Confirm min-stay policy values with the operator** before enabling Guesty
   `minNights` auto-push (unchanged from prior run; not touched this pass).
9. **S2 — Decide a `break_on_source_failure` threshold** (how many consecutive collector
   failures deprecate a signal) and wire `demote_on_source_break`, currently dead config.
10. **S2 — Add a cycle-level deadline to `src/signals/orchestrator.run_daily_cycle`** so
    one slow-but-alive external endpoint can't unboundedly extend an unattended
    `launchd` run.
11. **S2 — Validate `sanity_max_ratio_to_anchor: 3.0`** against at least one real
    high-demand week's actual pricing before this reaches `handle` in production.
12. **S3 — Eliminate the `datetime.utcnow()` deprecation warning** in
    `src/signals/store.py` (unchanged from prior run; still present, now surfaced by 8
    warnings instead of 4 as new tests exercise the same path).
13. **S3 — Add an explicit production/demo database marker** so a fresh/synthetic DB
    can't be mistaken for real health evidence (unchanged from prior run).
14. **S3 — Housekeeping**: remove `eval/backtest.run_backtest` (keep
    `score_signal_against_outcomes`, used by `promotion.py`); decide whether
    `signals/analyst.narrate_anomaly` should be wired into `weekly_brief` or removed;
    remove `signals/comp_movement.market_median_lift` (dead and measurably buggy);
    confirm `pms/webhooks.record_delivery`'s caller graph; retire the stale
    "PMS API can plug in later" claim in `src/ingest/`'s docstring; restore
    `Observation.observed_at` hour precision (needs a coordinated audit of every `as_of`
    call site first — not a quick fix).
15. **S3 — Placeholder owner names**: re-classified this pass, not a defect —
    operator-confirmed intentional per `config/portfolio/mont_luxe.yaml`'s own comment.
    Remove from future punch lists unless the operator says otherwise.

## Critic disposition

This synthesis, the five stage reports (each already carrying its own self-critic pass),
and the integration report were produced across five parallel isolated worktrees, merged
with one real (trivial, semantically-identical) conflict resolved by hand, and
re-verified as a whole (213 tests, mypy 2 errors, 80% coverage, preflight OK) before this
synthesis was written. No "pass" claim in this document was accepted from a stage
report's prose alone without this synthesis independently checking the report's own
described verification method (a pre-fix reproduction, a live trace, a repo-wide grep for
callers, or equivalent) was actually present in that report.

Per protocol, this synthesis was then submitted to a separate Critic agent — given the
document itself and full repo access, not this session's framing — before being treated
as final. The Critic independently re-derived and **confirmed** both S1-NEW findings from
code (constructing a live case for the rounding overrun; seeding a temp DB with a 4th
property and confirming an unscoped `recommend` run priced it), re-ran the full test/
mypy/coverage suite and confirmed the reported numbers on current `main`, spot-checked
two "Fix (done)" verdicts (guardrails sanity ceiling, retrospective.py) against the
actual pre-fix/post-fix code and regression tests, confirmed the severity ordering is
defensible, and confirmed no stage-agent cross-stage flag was silently dropped from the
punch list. The Critic found and this report has already corrected **one real error**:
the rounding bug's worst-case dollar impact was originally understated by 2x (`round_to/2`
stated, `round_to` actual, since the function only ever rounds in one direction per
branch) — fixed above in both the verdict and punch-list item #2. No other correction was
required; the Critic's full findings are preserved in this session's record for anyone
auditing this report's own production.
