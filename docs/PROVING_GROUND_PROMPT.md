# Mont Luxe Collection — Proving Ground: Research, Build, and Run the Definitive Test Environment

**Purpose of this document:** a standing prompt for a fresh agent team. Feed it verbatim.
It asks you to **research, design, build, and run** a point-in-time simulation and
stress-test environment ("the Proving Ground") for this repository. It is organized as a
**difficulty ladder**, from an easy level where every signal agrees to a level hard enough
to stump ordinary pricing software. It also runs an **independent, self-improving audit
loop**: the engine never grades itself, and every proposed fix reaches the operator in plain
language before anything changes.

The same evidence produces two outputs:

1. **An engineering audit.** Where the engine is wrong, brittle, or overconfident, and exactly
   what to fix.
2. **A customer-facing Evidence Pack.** Something a property-management company in a mountain
   market can read to see *what* was tested, *how*, on *which data*, *which levels the engine
   cleared*, and *where it lost*.

When the sales story and the engineering truth conflict, **honesty wins.** Every claim in the
Evidence Pack must trace back to a reproducible run.

This is intended to be the most comprehensive test and audit this repo has had. Do not
shortcut the research phase, the independence rules, or the sealed exams.

**But build the thin slice first.** Start with **Phase 0 (§1A)**: a working minimum spine
(runner, grader, one Fix Card, approval queue, receipt) before any large research or design
effort. If you hit any **stop condition (§1B)**, halt and ask. Working software that proves
the loop beats beautiful documents about a loop that doesn't exist yet.

---

## 0. Ground truth before you start

Read these in order. Don't relitigate locked decisions. Flag them if the Proving Ground
shows they cause wrong behavior, but don't override them.

1. `README.md`, `docs/LOCKED_INPUTS.md`, `docs/ARCHITECTURE.md`
2. `docs/rules/PRICING_DOCTRINE.md`, `docs/rules/AUTONOMY.md`, `docs/rules/COMP_DATA.md`
3. `docs/SIGNAL_FOUNDRY_RUNBOOK.md`, `docs/PFEIFER_OPTIMIZATION_RUNBOOK.md`,
   `docs/RESORT_INTELLIGENCE_RUNBOOK.md`, `docs/resort/WINTER_PARK_KNOWLEDGE.md`
4. `config/policies/*.yaml` (especially `conditions.yaml` for the SQI curve and kill switch,
   `markets.yaml` for the five Colorado markets and their SNOTEL stations, and `signals.yaml`
   for the promotion ladder), plus `config/portfolio/mont_luxe.yaml`
5. Existing evaluation machinery, which you **extend** and do not replace:
   - `src/eval/backtest.py`: leak-free replay, `assert_no_lookahead`, information coefficient, hit rate
   - `src/eval/retrospective.py`: honest Guesty retrospective and its stated limits
   - `src/eval/shadow.py`: forward shadow table
   - `src/signals/store.py`: the `as_of` / `observed_at` contract
   - `scripts/run_testruns.py` + `docs/testrun/`: blind→freeze→hash→reveal harness, and its
     `TESTRUN_AGENT_CMD` hook for launching independent agent sessions (Claude Code or Codex CLI)
   - `data/dec2023/`: a prior hand-built point-in-time market evaluation
6. Prior findings, so you don't re-flag settled items: `docs/reports/PRODUCTION_READINESS_AUDIT_2026-09-20.md`,
   `docs/reports/TESTRUN_FINAL_AUDIT_2026-09-25.md`, `docs/reports/GUESTY_RETROSPECTIVE.md`
7. `docs/PRODUCTION_READINESS_AUDIT_PROMPT.md`: its stage/critic structure is reused in §9
8. `git log --oneline -30`

**The moat.** Any competitor can scrape comp prices. What this engine has that they don't
is the Pfeifer Optimization signal layer:

- SNOTEL snowpack (`snotel`) feeding the Season Quality Index (`sqi`)
- CDOT / Berthoud Pass access risk (`cdot`, `access`)
- DEN air-capacity (`flight`)
- ENSO season-ahead prior (`enso`)
- Open-Meteo weather as a secondary input (`weather`)
- Resort operations (`resort`, `resort_ops`)
- Calendars, intent, regulatory supply
- Cross-valley substitution (`substitution`)

These modules get the **heaviest** testing. The rest of the repo still gets full coverage.

**Architectural invariant:** LLM agents never set prices. Collectors write observations,
deterministic builders write features, and only the guarded engine prices. Nothing in the
Proving Ground may give an agent a path to write a price, or to change `src/`, `config/`, or
`docs/rules/`, without the operator approval gate in §10.

---

## 1. Non-negotiable rules

1. **Free data and free tools only.** Use only public, no-cost data sources and open-source
   libraries. Before using any source, check its terms, **including whether commercial use
   is allowed**. The Evidence Pack is sales material. For example, Open-Meteo's free tier
   is for non-commercial use, so decide and document whether internal testing qualifies, and
   what would change if results were published. If a source is paid, gated, or its ToS
   forbids the use, mark it `unavailable` and design around it. Keep a
   `SCALE_UP_OPTIONS.md` listing paid sources that would strengthen results later (AirDNA,
   OpenSnow, commercial weather tiers, the Google Trends API alpha), but don't use them.
   The only compute and model access allowed is what the operator already has: the local
   machine plus the existing Claude Code and Codex CLI sessions.
2. **Zero Guesty writes.** Every run uses `--adapter dry_run` against a disposable DB. The
   final report must state `Guesty write count: 0`.
3. **Point-in-time or it didn't happen.** Every datum the engine sees on simulated day `D`
   must have been *publicly knowable* on `D`: `published_at <= D`, not just
   `effective_date <= D`. Use real publication lags and keep revision vintages. (The
   finance analogue is ALFRED vs FRED.)
4. **The engine never grades itself.** See §9. Worlds, exams, and scoring are authored and
   owned by roles that cannot modify the engine. The roles that modify the engine can't
   see or modify the exams, worlds, or scoring.
5. **Multiple worlds, not one.** At least three structurally different demand worlds (§4.3).
   A level counts as cleared only if it's passed in **every** applicable world.
6. **Sealed exams.** Every level has an open **practice set** and a sealed **exam set**. The
   final exam is a one-season, one-market **lockbox** that runs once, at the end.
7. **Real vs synthetic is always labeled.** Real history, real signals replayed
   point-in-time, perturbed real data, and fully synthetic worlds must be distinguishable
   in every table and chart. Never present simulated revenue as realized revenue.
8. **Failures are first-class output.** Failed levels, calibration misses, and signals that
   added nothing go in the Evidence Pack. Don't delete them or move them to an appendix.
9. **Reproducible.** Every run is seeded, config-hashed, and input-hashed. It is
   re-runnable with one command and produces byte-identical frozen exports.
10. **Every result carries an evidence label.** The label is inherited from the *most
    restrictive* source that fed it:
    - `publishable`: every input is licensed for commercial use and the claim follows the
      §11 language rules.
    - `internal_only`: at least one input is non-commercial or has unclear ToS (e.g.,
      Open-Meteo free tier), or the result depends on a simulated world that hasn't been
      disclosed yet.
    - `excluded_from_sales_claims`: publishable data, but the result is exploratory,
      failed its level, or comes from a practice set.

    The Evidence Pack generator **refuses** to include anything not labeled `publishable`.
    Labels are stored in the run manifest, not added by hand.
11. **Simulated money is always hedged.** Simulated revenue or lift is phrased as "in the
    simulated world, the engine earned…". It is never phrased as "would have earned" or
    "will earn". Real-money claims come only from real history or the live forward test.

---

## 1A. Phase 0: Minimum viable Proving Ground (build this first)

Before the big research phase, prove that the spine works end to end. **Phase 0 must be
finished before Phase R begins.** Its job is to show that the runner, grader, approval
queue, and receipt loop all work before anyone designs the full system.

**Scope (and nothing more):**

1. **Level 1:** one synthetic calm season for Winter Park (`grand_home`), Nov 1–Apr 15.
2. **One real Level 2 season:** pick the season whose Berthoud Summit SNOTEL peak SWE is
   closest to median. For the MVP, use only public-domain federal sources already reachable
   from the repo's collectors:
   - NRCS SNOTEL (`publishable`)
   - NOAA CPC ENSO (`publishable`)

   All other signals are `unavailable` for the MVP. That's fine; say so.
3. **One demand world (W1),** authored in a separate agent session that can't see engine
   internals (§9), even in the MVP.
4. **A deterministic runner** for the §4.1 day-by-day loop, using `--adapter dry_run`.
5. **A deterministic scorer** using the §5.4 default thresholds for L1/L2. Baselines:
   - flat seasonal
   - comp-median follower (if comps exist; otherwise say so)
   - engine with the moat off
   - oracle
6. **Guards:**
   - one lookahead canary
   - a Guesty-write counter
   - a same-seed determinism check
7. **One audit pass** by one auditor session.
8. **One real Fix Card** in the §10.3 format, plus an `APPROVAL_QUEUE.md` containing it.
9. **The receipt loop exercised once.** If the operator approves the card, apply it on a
   branch, re-run, and write the receipt. If they reject it, write a receipt recording the
   rejection. Either way, the loop has run.
10. **An Evidence Pack stub:** section headings, the one L1/L2 result with its evidence label,
    and the reproduce command.

**Phase 0 acceptance tests: the harness must prove it can fail.** A harness that can only
say PASS is worthless. These are required tests in `tests/proving_ground/`. Phase 0 is not
done until all of them exist and pass:

1. **The real engine runs.** Engine prices come from the production pipeline: the same
   functions `wp-price recommend` uses (ceiling → bookprob → compose → guardrails), running
   against a disposable DB that the world populates.
   - A test asserts that the engine-side module never reads world internals: no oracle
     price, no true demand, no world parameters. It also asserts that
     `proving_ground_exam/worlds/` never imports engine modules.
   - **Deriving the engine's price from the oracle, the world, or a constant is an automatic
     S1 failure of the harness.**
2. **Sabotage tests (known-bad must fail):**
   - a deliberately broken engine (e.g., always prices at floor, or SQI sign flipped) **FAILS L1**
   - a random-price policy **FAILS L1**
   - the oracle **PASSES L1**
3. **Every hard gate is measured, not asserted:**
   - A planted future-dated canary observation **trips** the lookahead gate.
   - A test adapter that attempts a PMS write **trips** the Guesty-write gate.
   - A price outside `[floor, ceiling]` **trips** the guardrail gate.
   - Determinism means actually running twice and comparing hashes: same seed gives
     identical hashes, a different seed gives different hashes.
   - No gate's `observed` or `passed` value may be a literal. Each gate records a
     `measured_by` field naming the function that measured it, and a test enforces this.
4. **The world can tell policies apart.** On L1, flat-seasonal regret must exceed oracle
   regret by at least 5 percentage points. Otherwise the world is too flat to test anything,
   and the Examiner must rebuild it.
5. **L2 is real and historical.**
   - The season is a completed one (2025-26 or earlier).
   - The SNOTEL and ENSO inputs are actually downloaded files, listed in the manifest with
     URL, retrieval timestamp, `published_at`, and SHA-256.
   - A test re-hashes them.
6. **Evidence labels are computed** from the source manifest's licenses, never written as
   literals. A test asserts that a run with any `internal_only` source can't be labeled
   `publishable`.
7. **Honest completion report.** The final message lists every exit criterion and every
   acceptance test with the file path that proves it, plus a
   **"What is still fake or stubbed"** section. Claiming "complete" while any item is
   stubbed is itself an S1 finding.

**Phase 0 exit criteria:**

- `wp-price proving-ground run --level 1` and `--level 2` each work with one command
- two runs with the same seed produce identical hashes
- the scoreboard shows the engine against at least two baselines
- the operator has read one real Fix Card and recorded a decision

**Time box: ~2 working days of agent effort.** If it runs over, stop and report what's
blocking (§1B). Don't write research docs during Phase 0 beyond what the MVP needs.

---

## 1B. Stop conditions: halt and ask the operator

Stop, write a short `BLOCKED.md` (what, why, options, recommendation), and wait. Don't work
around the problem when any of these come up:

- **License ambiguity:** you're not sure whether a source allows the intended use.
- **No point-in-time source:** a moat signal needed by a level has no as-issued archive,
  and neither reconstruction nor synthetic forecast error is clearly acceptable.
- **The real engine can't be connected:** you can't make the actual pricing pipeline run
  inside the harness. **Don't substitute a stand-in** (such as oracle × constant). Stop and
  report what blocks it.
- **The harness needs production code changed:** anything in `src/` (outside
  `src/proving_ground/`), `config/`, or `docs/rules/`. That's a Fix Card, not a harness
  change.
- **No monotone hardness:** baselines fail to show monotonically increasing difficulty
  after two examiner rebuild attempts.
- **Isolation can't be enforced:** sealed-exam or role isolation can't be enforced with the
  local tooling (§9).
- **Determinism fails:** the same seed produces different outputs, and the cause isn't
  found within a reasonable effort.
- **Guesty write risk:** any code path that could write to Guesty, even in dry-run.
- **Any cost above $0.**
- **A time box is exceeded:** Phase 0, or a single improvement cycle running over its budget
  in `DESIGN.md`.

---

## 2. Phase R: Research (breadth is mandatory)

Don't come back having read one or two sources. For **each** track below, examine at least
**five** distinct sources. Record each in `docs/proving_ground/RESEARCH_LOG.md` with:

- the URL
- what it is
- what you'd borrow, and what you'd reject and why
- the **cost and license**
- a **clone / vendor / borrow-pattern / reject** verdict

The leads below were gathered 2026-09-25. They're starting points, not conclusions.
Verify every one yourself.

### Track A: Simulation and backtest frameworks to clone or borrow from

Question to answer: *can anything be cloned wholesale?* The expected answer is "no; borrow
patterns." Prove or disprove it.

| Lead | Why it's relevant |
|------|-------------------|
| [PassengerSim](https://github.com/PassengerSim/passengersim) | Airline RM simulator. Customer-choice and booking-curve demand. The core library isn't public. |
| [airsim/tvlsim](https://github.com/airsim/tvlsim), [airsim/rmol](https://github.com/airsim/rmol) | Amadeus-origin open travel-market simulator (GPL-3). Watch the license if you vendor it. |
| [ABIDES](https://github.com/abides-sim/abides), [abides-jpmc-public](https://github.com/jpmorganchase/abides-jpmc-public) | Discrete-event, agent-based kernel with a Gym wrapper. Guests and competitors as independent actors. |
| [Open Bandit Pipeline](https://github.com/st-tech/zr-obp) | Off-policy evaluation: valuing a new pricing policy from logs produced by the old one |
| [awesome-dynamic-pricing](https://github.com/DallasBuyer/awesome-dynamic-pricing), RL pricing Gym envs | Mostly toy demand. Useful as **baseline opponents**, not as the world. |
| [skforecast](https://skforecast.org) / sktime | Rolling-origin and walk-forward backtesting patterns |
| Mesa (Python ABM) | Lighter-weight alternative to ABIDES |

### Track B: Point-in-time historical data ("what was known, when"), all free

| Signal | Observed truth | As-issued / vintage source (leads) |
|--------|---------------|-----------------------------------|
| Snowpack | NRCS AWDB REST (SNOTEL) | AWDB water-supply forecasts; provisional vs revised flags |
| Weather / snowfall | Open-Meteo archive | [Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) (~2022+), [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api). **Check the commercial-use terms.** |
| NWS forecasts / warnings | — | [IEM NWS text archive](https://mesonet.agron.iastate.edu/nws/text.php) (forecast discussions, winter storm warnings; VTEC-complete since 2005) |
| ENSO | CPC ONI | [CPC ENSO Diagnostic Discussion archive](https://www.cpc.ncep.noaa.gov/products/expert_assessment/ENSO_DD_archive.php) + probability forecasts as issued |
| Berthoud / US-40 | [isberthoudpassopen.com closure history](https://isberthoudpassopen.com/closure-history/), CDOT press archive | Dated press releases. Reconstruct and label the result. |
| Traffic demand proxy | [CDOT Traffic Data Explorer](https://dtdapps.codot.gov/otis/trafficdata), [Eisenhower Tunnel counts](https://www.codot.gov/travel/ejmt/trafficcounts) | Publication lag |
| Air capacity | [BTS T-100 segment](https://www.transtats.bts.gov) (DEN, HDN, EGE, GUC) | Release lag |
| Airport throughput | [DEN monthly reports](https://www.flydenver.com/about-den/governance/reports-and-financials/) | Release dates |
| Resort ops | Resort snow reports; [OnTheSnow history](https://www.onthesnow.com/colorado/winter-park-resort/historical-snowfall) | Dated press. Check the ToS before scraping. |
| Avalanche / hazard | [CAIC](https://avalanche.state.co.us/) historic forecasts (`?date=`) | — |
| Search intent | Google Trends: the official API is a gated alpha and pytrends was archived, so likely `unavailable` under the free-only rule | — |
| Market / comps | Existing `market_snapshots`, `data/dec2023/`, Inside Airbnb (Denver, free) | Snapshot date = vintage |
| Lodging demand truth | Grand County / Winter Park lodging- and sales-tax collections | Release lag |
| Own history | Guesty history via existing sync (read-only) | `retrospective.py` limits |

Deliverable: `docs/proving_ground/DATA_SOURCES.md`, listing per signal:

- the source
- cost ($0, or the reason it's excluded)
- license, including commercial use
- coverage years
- publication lag
- whether values get revised
- how the vintage is stored

Where no as-issued forecast archive exists, say so. Then pick one of these and label it:
reconstruct it from dated text products, or synthesize it by adding calibrated forecast
error to the truth.

### Track C: Testing techniques

- [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing
- Metamorphic testing ([Giskard](https://www.giskard.ai/knowledge/how-to-test-ml-models-4-metamorphic-testing), arXiv surveys)
- [mutmut](https://github.com/boxed/mutmut) / [Cosmic Ray](https://cosmic-ray.readthedocs.io/) for mutation testing
- [VCR.py](https://vcrpy.readthedocs.io/) + pytest-recording for cassette replay
- time-machine / freezegun
- [pandera](https://pandera.readthedocs.io/) data contracts
- [Evidently](https://github.com/evidentlyai/evidently) drift reports
- [SDV](https://github.com/sdv-dev/SDV). Beware: a synthesizer fit to Guesty history can leak
  the engine's own biases into the world.
- Fault injection for hung, partial, and slow endpoints (`scrape-properties` hung in the last testrun)

### Track D: How to present evidence buyers will trust

- **SR 11-7 (Fed/OCC model-risk guidance):** conceptual soundness, ongoing monitoring,
  outcomes analysis. This is the skeleton of the Evidence Pack.
- **Backtest-bias taxonomies from quant finance** (survivorship, lookahead, overfitting):
  name each bias and say how it's prevented.
- **Competitor claims (PriceLabs, Beyond, Wheelhouse):** mostly before/after with no
  counterfactual. State specifically how the Proving Ground is stronger.
- **Model cards / datasheets** for the provenance appendix.
- **Belt/level certification formats** (ski-run ratings, security certification levels):
  how to present "cleared Level 4 of 6" so a non-technical buyer understands it immediately.

### Track E: Self-improving loops and independent evaluation

Find what makes a self-improving loop work *without* the system grading itself. Starting
leads:

| Lead | Pattern to borrow |
|------|-------------------|
| [Darwin Gödel Machine](https://github.com/jennyzzt/dgm) ([paper](https://arxiv.org/abs/2505.22954)) | Replaces "prove it's better" with **empirical validation on a benchmark**, and keeps an **archive of variants** instead of overwriting. Use this as the model for the engine-version archive (§10). |
| [OpenEvolve](https://huggingface.co/blog/codelion/openevolve) (open AlphaEvolve) | Generator → **separate evaluator pool** → program database. A pattern for searching config parameters, with outputs used only as proposals. |
| [Voyager](https://arxiv.org/abs/2305.16291) | **Automatic curriculum** plus a skill library stored as executable code. The model for the difficulty ladder and the harness playbook. |
| [Reflexion](https://arxiv.org/abs/2303.11366) | Verbal post-mortems in episodic memory |
| [Hermes Agent](https://github.com/nousresearch/hermes-agent) | Closed loop: solve → document → retrieve → improve |
| [AI Scientist v2](https://pub.sakana.ai/ai-scientist-v2/paper/paper.pdf) | An **ensemble of independent reviewers** with an area-chair decision |
| LLM-as-judge self-preference bias ([arXiv 2604.22891](https://arxiv.org/html/2604.22891v4)) | Models favor their own outputs, so use **cross-model judging** (Claude ↔ Codex) |
| Reward hacking in coding agents ([Cursor](https://cursor.com/blog/reward-hacking-coding-benchmarks), [SpecBench](https://arxiv.org/html/2605.21384v1), ImpossibleBench) | Agents edit tests and hard-code answers, and visible/held-out splits catch it. This is why fixers can't see exams. |
| Skill misevolution ([arXiv 2608.12851](https://arxiv.org/pdf/2608.12851)) | Self-written lessons drift into unsafe behavior, which is why human approval is required |

Deliverable: a section of `DESIGN.md` that says which of these patterns the Proving Ground
adopts, for which role, and which failure mode each one guards against.

**Phase R exit:** a `DESIGN.md` covering:

- the research verdicts
- data availability and cost per signal
- the world-model specs
- the full level specs (§5), including each level's practice and exam composition
- the pass thresholds per level
- the lockbox choice and its hash
- the role map (§9)
- an effort estimate

**Stop and present `DESIGN.md` to the operator for approval before building.** Use the
plain-language format of §10.4 for the summary.

---

## 3. Target layout

Adjust the names if research argues for something better. Keep the separation. It's what
enforces §9.

```
src/proving_ground/            # HARNESS (runner-owned): runs the engine day by day; imports src/*
  timemachine/                 # vintage store: (source, key, effective_date, published_at, value, vintage_id)
  replay/                      # collectors in replay mode — same code path as live
  runner/                      # deterministic season loop; no LLM anywhere in here
proving_ground_exam/           # EXAMINER-OWNED — engine-side roles may not read the exam/ subfolders
  worlds/                      # W1–W4 demand worlds — must NOT import src.bookprob/elasticity/compose/conditions
  competitors/
  levels/L1..L6/practice/      # visible scenario specs
  levels/L1..L6/exam/          # sealed specs; only hashes committed until reveal, or generated from a runner-held seed
  scoring/                     # metrics, baselines, oracle, thresholds — hash-locked
data/proving_ground/
  vintages/  cassettes/  runs/<run_id>/  archive/<engine_version>/
docs/proving_ground/
  RESEARCH_LOG.md  DATA_SOURCES.md  DESIGN.md  SCALE_UP_OPTIONS.md
  LEVELS.md  SCOREBOARD.md  LESSONS.md  PLAYBOOK.md
  proposals/FIX-###.md  APPROVAL_QUEUE.md  receipts/FIX-###-receipt.md
  AUDIT_REPORT.md  EVIDENCE_PACK.md
tests/proving_ground/          # tests of the harness itself
```

Add CLI entry points to `wp-price proving-ground`: `build-vintages`, `run --level N [--exam]`,
`score`, `scoreboard`, `audit`, `queue`, `apply FIX-###` (refuses without a recorded
approval), and `lockbox --i-understand-this-is-one-shot`.

Add guard checks (tests + a pre-commit or CI script):

- `proving_ground_exam/` never imports the forbidden engine modules
- a fix branch's diff never touches `proving_ground_exam/`, `tests/proving_ground/`, or scoring thresholds
- exam hashes match

---

## 4. The environment

### 4.1 The daily loop

For each simulated day `D` of a season (for example, Aug 1 to Apr 30):

1. The time machine exposes only data with `published_at <= D` to the replay collectors.
2. The real `wp-price` pipeline runs as in production:
   snapshot → signals cycle → features → comps → ceiling → bookprob → compose →
   guardrails → explain, with the `dry_run` adapter. There's no special test path. If the
   engine needs a hook to be testable, that's a finding.
3. The world takes the engine's prices, competitor prices, and the *true* conditions for `D`.
   It generates booking requests, bookings, cancellations, and length-of-stay patterns, and
   feeds them back as simulated Guesty reservations.
4. Competitor agents reprice.
5. Everything is logged for scoring and for the auditors.

### 4.2 Two data layers

- **Signal layer:** real, replayed point-in-time (or perturbed / synthesized at higher
  levels, and labeled as such).
- **Guest layer:** always simulated, because nobody knows how many families *would have*
  booked at a different price. Calibrate it to real anchors:
  - Guesty realized occupancy and ADR
  - Eisenhower Tunnel and DEN volumes
  - lodging-tax seasonality
  - `data/dec2023` comp ranges

  Never present it as observed.

### 4.3 Demand worlds (examiner-authored, at least three, plus an adversarial one)

- **W1: discrete choice.** Lead-time Poisson arrivals, multinomial logit against the comp set
  with an outside option, heterogeneous sensitivity to *true* conditions.
- **W2: segment mix.** Holiday families with fixed dates, late-booking powder-chasers, groups,
  and summer travelers, each with its own elasticity and condition response.
- **W3: empirical resample.** Real booking curves bootstrapped, with price response taken
  from external literature (not from the engine's config).
- **W4: adversarial.** Built to break the engine's assumptions:
  - non-monotone condition response
  - demand that reacts to forecasts rather than outcomes
  - elasticity that flips near psychological price points

For each world, document every assumption, its source, calibration fit, and what the author
was allowed to read.

### 4.4 Competitor agents

- a static owner
- a PriceLabs-style occupancy repricer
- a panic discounter (−30% at 14 days out)
- a median follower
- at higher levels, a **strategic** competitor that learns the engine's reactions and
  exploits them

### 4.5 Baselines and oracle

These are examiner-owned and double as the "ordinary pricing software" the top levels must
stump:

1. What Mont Luxe actually charged (real history, where seasons overlap)
2. Flat seasonal pricing
3. Comp-median follower
4. Generic dynamic heuristic (occupancy × lead time, PriceLabs-like)
5. A simple RL/bandit pricer from Track A
6. **The engine with the moat off** (`sqi.enabled: false`, collectors disabled). This isolates
   what the moat is worth.
7. **Oracle:** the true demand curve is known inside a simulated world, so report **regret**
   against the RevPAN-optimal price.

---

## 5. The difficulty ladder

Seasons, markets, worlds, and scenarios combine into six levels, rated like ski runs so a
property manager instantly understands the difficulty. **Each level is harder than the last
in a measurable way, not just by assertion.**

### 5.1 How difficulty is measured

For every level, the examiner computes a **legibility profile** and publishes it in `LEVELS.md`:

| Dial | Meaning | Easy → Hard |
|------|---------|-------------|
| Signal agreement | Share of moat-signal pairs pointing the same direction for demand | ~100% → near-random or deceptive |
| Signal informativeness | How much of the world's true demand variation the observable signals explain | High → low, or *misleading* |
| Forecast skill | As-issued forecast error vs truth | Perfect → real busts → adversarial busts |
| Data completeness and freshness | Outages, staleness, revisions, late publication | Complete → heavy faults |
| Novelty | Distance from any season or market in the practice sets | In-distribution → never-seen shocks |
| Stationarity | Whether relationships stay fixed within the season | Fixed → regime change mid-season |
| Competitor behavior | How rational and stable the comps are | Stable → strategic and exploitative |
| History available | Own and market history | Multi-year → cold start |

**Hardness verification:** a level only counts as hard if it measurably is. Run every
baseline (§4.5) on every level. Requirements:

- baseline regret must rise monotonically from L1 to L6
- at **L5 and L6, at least four of the five non-engine baselines must fail** the level's
  pass thresholds

If ordinary pricing software passes L6, the examiner must make L6 harder before the engine
attempts it. The point of L6 is to stump normal price-optimization software.

### 5.2 The levels

Classify every real season **from the data itself** (SNOTEL % of median, ENSO state, closure
counts, forecast error), not from memory. Candidate seasons are ~2020-21 through 2025-26.
Markets come from `markets.yaml`: `grand_home` (Winter Park), `grand_valley`, `summit`,
`clear_creek_eagle`, `routt` (Steamboat).

**🟢 Level 1 — Bunny Hill ("everything agrees").**
- **Season:** a synthetic climatology season built from real medians. Snowpack tracks median
  exactly, forecasts are perfect, flight capacity is flat year over year, there are no
  closures, comps are stable, and data is complete.
- **Setup:** Winter Park only, world W1, all lead times.
- **What it tests:** sanity and calibration. Every signal tells the same story.
- **Pass:** near-oracle regret, zero guardrail or autonomy incidents, and P(book) well
  calibrated. **If the engine fails L1, stop everything and fix that first.**

**🟢 Level 2 — Groomer ("real but calm").**
- **Season:** the most median, least eventful real season, replayed point-in-time with
  natural forecast noise.
- **Setup:** Winter Park, worlds W1 and W2.
- **What it tests:** real-data plumbing, publication lags, vintages, and the lead-time grid.

**🔵 Level 3 — Moguls ("real variety, signals still mostly agree").**
- **Seasons:** a strong snow year, a weak year, and an average year. Signals agree on
  direction but differ in magnitude.
- **Markets:** Winter Park plus Summit and Steamboat, **with no retuning**.
- **Setup:** worlds W1–W3.
- **Faults:** short station outages, which must become `unavailable` and never zero-filled.
- **What it tests:** generalization across markets, and whether the moat adds value over
  the moat-off baseline.

**⚫ Level 4 — Chutes ("real conflicting signals").** Real historical conflicts:
- the 2025-26 drought, where Berthoud Summit SNOTEL read ~60% of normal and Open-Meteo
  reanalysis read ~91%
- forecast busts found in the IEM forecast-discussion archive
- an early big-snow bait followed by a dry January
- a Berthoud closure on a peak-weekend arrival day
- air capacity up while other demand proxies are down
- a competitor panic-discounting into good conditions

Plus moderate perturbations: a station reading 15% low, a delayed release, a retroactive
revision. All five markets. Worlds W1–W3.

**What it tests:** which signal the engine trusts when they disagree, and whether it chases a
depressed comp signal (the `AUTONOMY.md` risk).

**⚫⚫ Level 5 — Cornice ("adversarial").**
- world W4
- silent staleness (a value frozen for 10 days while still reporting `ok`)
- jointly impossible signal pairs
- **concept drift:** a signal that predicted demand in the practice seasons reverses in the exam
- a strategic competitor that baits the engine
- stacked data faults: a comp scrape returning 3 listings, a resort HTML layout change, a
  hung endpoint, currency and format errors
- lookahead canaries: poisoned future-dated observations
- a **cold-start market** with minimal history

**What it tests:** robustness, fault handling, leak-proofing, and humility under uncertainty.

**🟥 Level 6 — Out of Bounds ("stump the market").** Built to defeat ordinary pricing software:
- stacked, never-coded shocks mid-season: wildfire smoke, a lift strike, a 5-day US-40
  avalanche closure, a pandemic-style collapse and snap-back, a 25% luxury-demand recession
  during excellent snow, a new 30-home luxury development entering the comp set, a
  lodging-tax or STR-cap change
- **regime change** within a season
- multiple sources wrong at once
- **ambiguous ground truth:** two plausible worlds are consistent with everything observable,
  so the engine must hedge
- a market with no nearby SNOTEL station
- historical analogs that point the wrong way

**What passing means:** the engine can't be expected to price L6 perfectly. It passes by:
1. detecting that it's out of distribution, and how quickly
2. widening its uncertainty and demoting autonomy (no auto-push through a novel shock)
3. explaining the uncertainty in plain language
4. keeping worst-case loss bounded
5. still beating the baselines on regret

### 5.3 Practice, exam, and certification

- Each level has a **practice set**, which is visible to the fixers, and a **sealed exam
  set** with different seasons, markets, perturbation draws, and scenario instances.
- Exam sets are regenerated from a fresh runner-held seed **every improvement cycle**, so
  no fix can memorize them.
- A level is **cleared** when the engine passes its exam in every applicable world, on two
  consecutive fresh exam draws.
- **Regression rule:** every fix must re-run *all* levels. A fix that clears L5 but drops
  L3 is rejected.
- `SCOREBOARD.md` shows, per engine version: levels cleared, per-level metrics, and baseline
  comparisons. Think of it as the belt chart for the Evidence Pack.
- Pass thresholds for every level are written into `DESIGN.md` **before** any run and
  hash-locked. Changing one requires an operator-approved Fix Card explaining why.

### 5.4 Default pass thresholds (placeholders you revise in Phase R, then lock)

These defaults exist so scoring is never vague. Phase R may revise them with evidence, and
the operator approves the final table. After that they're hash-locked.

"Regret" is `(oracle RevPAN − engine RevPAN) / oracle RevPAN` over the scored nights.
"Best baseline" is the best non-oracle, non-engine baseline in that world.

**Hard gates, every level, every run.** Any single violation fails the run:

| Gate | Threshold |
|------|-----------|
| Lookahead violations (canaries + `assert_no_lookahead`) | 0 |
| Guesty / non-dry-run write attempts | 0 |
| Guardrail violations (price outside `[floor, ceiling]`, invariant breaches) | 0 |
| Auto-pushes while data health is failing | 0 |
| Same-seed determinism | Identical output hashes |

**Per-level defaults:**

| Level | Regret vs oracle | vs baselines | P(book) calibration | Tail / safety | Humility (§7) |
|-------|------------------|--------------|---------------------|---------------|---------------|
| L1 | ≤ 5% | ≥ best baseline | Brier ≥ 20% better than a flat base-rate predictor | Day-over-day churn ≤ 5% median | False-alarm rate ≤ 5% |
| L2 | ≤ 10% | ≥ best baseline in every world | Brier ≥ 15% better | Worst-10-nights loss ≤ best baseline's | False-alarm rate ≤ 5% |
| L3 | ≤ 15% | Beats moat-off with 80% CI excluding 0 in ≥ 2 of 3 markets; never > 3% below best baseline in any market | Brier ≥ 10% better | Worst-10 ≤ 1.1× best baseline's | False-alarm rate ≤ 10% |
| L4 | ≤ 20% | ≥ best baseline in ≥ 80% of scenarios | Brier ≥ 5% better | Worst-10 ≤ 1.25× best baseline's; max peak-night underprice ≤ 20% | ≥ 0.5 |
| L5 | ≤ 30% | ≥ median baseline in every scenario | Reliability curve reported; no metric target | Fault → advisory within the documented grace period; worst-10 ≤ 1.5× best baseline's | ≥ 0.7 |
| L6 | ≤ the best baseline's regret | Beats ≥ 4 of 5 baselines on regret | Reported only | No auto-push after detection; worst-10 ≤ 2× oracle loss | ≥ 0.8; OOD detected within 3 simulated days of shock onset |

Cleared = every hard gate passes, and every column in the level's row passes, in every
applicable world, on two consecutive fresh exam draws.

### 5.5 Reading results: the outcome truth table

Scoreboard, auditors, and Fix Cards all use this table so the same result always means the
same thing:

| Result | Meaning | Action |
|--------|---------|--------|
| Pass practice, fail exam | Likely overfit | Reject or redesign the fix |
| Pass a higher level, fail a lower one | Regression | Reject the fix |
| Engine passes and baselines also pass | Level too easy | Examiner rebuilds the level (hardness verification) |
| Engine fails but detects uncertainty in time (humility ≥ threshold) | Partial credit (L5–L6 only) | Propose a safety or pricing fix; the level is not cleared |
| Engine fails without detecting uncertainty | Unsafe failure | S1 Fix Card |
| Engine passes but humility false-alarm rate too high | Crying wolf | Fix Card; the level is not cleared |
| Any hard gate violated | Broken run | S1 finding; stop the cycle until fixed |
| Evidence depends on a non-commercial source | `internal_only` | Exclude from the Evidence Pack |
| Improvement shows up only in simulated worlds, not in replayed real data or the Guesty retrospective | Possible sim-to-real gap | Flag on the Fix Card; the Critic must address it |
| Two auditors disagree on the root cause | Unresolved | Area chair decides, or it's escalated to the operator on the card |

Target: at least 60 scenario instances across the ladder, with at least 60% exercising moat
signals. Include one **live forward-test** protocol for the 2026-27 season using
`src/eval/shadow.py`: daily frozen and hashed recommendations, published before outcomes
are known. It's specified but not auto-enabled. It's the only evidence that isn't simulated,
so recommend a start date.

---

## 6. Test layers across the whole repo

Produce a coverage matrix (`module × layer`) in `AUDIT_REPORT.md`. Moat modules get every
layer. Everything else gets at least unit + contract + property.

| Layer | Notes |
|-------|-------|
| Unit / contract | pandera schemas at stage boundaries; collector `FieldSpec` bounds; "reject, never clamp" |
| Property-based | `rec ∈ [floor, ceiling]` after rounding; SQI never zero-fills; guardrails can't be bypassed |
| **Metamorphic relations** | See below |
| Lookahead canaries | On every read path, including comps and pacing |
| Mutation testing | Over `src/signals/`, `ceiling/`, `compose/`, `guardrails/`, `leakage/`. Kill the surviving mutants that matter. |
| Cassette replay | Real + mutated responses for every collector |
| Fault injection | Timeouts, partial responses, hangs. Must degrade to advisory, never crash or push. |
| Signal ablation / attribution | Per signal × season × level: the dollar value of each piece of the moat |
| Drift / OOD detection | Detection rate and latency at L5–L6 |
| End-to-end ladder runs | §5 |

**Metamorphic relations** (holding everything else fixed). Derive more:

- More SWE never lowers the ceiling or price for a peak ski night.
- `berthoud_closed=1` on arrival day never raises P(book) for that arrival.
- Shifting a scenario by 364 days gives the same output, apart from explained holiday effects.
- Scaling all prices by `k` scales recommendations by ≈`k`, apart from documented absolute guardrails.
- Duplicating a comp moves the percentile by no more than the tolerance.
- Collector run order has no effect.
- Dropping an unavailable SQI component is the same as it never existing.
- An unpromoted new `signal_key` has zero effect on price.

---

## 7. Metrics

Report every metric per **level × season × world × market × lead time**, with bootstrap
confidence intervals. Never report one pooled number without the breakdown behind it.

| Metric | Notes |
|--------|-------|
| RevPAN vs each baseline | Primary |
| Regret vs oracle | Simulated worlds |
| Moat value | Engine minus moat-off, plus per-signal ablation |
| P(book) calibration | Brier score, reliability by lead time |
| Tail loss | Worst-10-nights; max peak-night underprice |
| Robustness | Degradation slope as perturbation strength rises |
| Safety | Guardrail violations = 0; pushes during a data-health failure = 0; OOD detection rate and latency |
| Explanation fidelity | Do the `explain` reasons match what ablation says moved the price? |
| Stability | Day-over-day price churn |
| **Humility (`uncertainty_quality`)** | See below |

**Humility score.** At L5–L6, the engine earns credit for knowing when it doesn't know. For
each injected shock or conflict event `e`, look at the window between shock onset and the
**damage point** (the first night where engine loss vs oracle exceeds the level's tolerance):

```
uncertainty_quality(e) = 0.4 · [autonomy demoted (handle → suggest/escalate) before damage point]
                       + 0.3 · [price range widened by ≥ the configured band before damage point]
                       + 0.3 · [explanation names the uncertainty or conflict in plain words before damage point]
```

The level score is the mean over events. The explanation check uses a blind rubric scored by
a cross-model judge ensemble (§9). Everything else is deterministic.

**Humility has to be paired with a false-alarm rate:** the share of L1–L3 nights where the
engine demoted autonomy or widened ranges with nothing actually wrong. An engine that always
says "I don't know" scores perfect humility and is useless. Both numbers appear on the
scoreboard, and §5.4 gates both.

---

## 8. Scenario specs

Each scenario is a YAML spec (examiner-owned) containing:

- level
- base season and market
- world(s)
- perturbation operators
- affected signals
- legibility-dial settings
- the expected **behavior class** (e.g., "raise holiday ceiling," "demote to suggest," "hold
  price and widen range"), not an exact price

`SCENARIOS.md` indexes the practice scenarios. Exam scenarios are indexed by hash only until
revealed after grading.

---

## 9. Independence: nobody grades their own homework

The engine and the agents that improve it are **never** the ones that write the exams,
define the worlds, run the scoring, or decide whether a fix worked. Split the work into
roles. Each role is a **separate agent session with its own context**, launched through the
existing `TESTRUN_AGENT_CMD` pattern. Where possible, use a **different model family** for
roles that judge each other: for example, Claude Code for the Fixer and Codex CLI for the
Auditor/Critic, or the reverse. That reduces shared blind spots and self-preference bias. If
only one model family is available, use fresh sessions with no shared context and mark the
reduced independence in the report.

| Role | Does | May read | May write | Never |
|------|------|----------|-----------|-------|
| **Operator** (human) | Approves the design, thresholds, and every fix | Everything | Approvals | — |
| **Examiner** | Builds worlds, competitors, baselines, oracle, levels, exams, thresholds | External research, public engine *interfaces* (CLI, DB schema), level results | `proving_ground_exam/` | Read engine internals (`bookprob`, `elasticity`, `compose`, `conditions.yaml` curves); see Fix Cards before exams are sealed |
| **Runner** | Executes the ladder. **Deterministic code, not an LLM.** | Everything it needs to run | `data/proving_ground/runs/` | Make judgments |
| **Grader** | Scores runs against hash-locked thresholds. **Deterministic code.** LLM judging only for explanation quality, via a blind rubric and cross-model ensemble. | Run outputs, thresholds | `SCOREBOARD.md` | Change thresholds |
| **Auditor(s)** | Comprehensive audit of each run and of the repo (§10.2). Root causes. Two independent auditors from different model families, reconciled by an **area-chair** step. | Run logs, code, docs, practice sets | `LESSONS.md`, audit findings | Write fixes; see exams before grading |
| **Fixer / Proposer** | Turns findings into Fix Cards and, *after approval*, implements them on a branch | Engine code, practice sets, findings | `proposals/`, fix branches | Read `levels/*/exam/`; edit exams, worlds, scoring, or harness tests |
| **Critic / Red team** | Attacks each Fix Card: is it overfit, is it a hack that games the metric, does it break doctrine? Tries to build a new scenario the fix fails. | Fix Cards, practice sets | Critique on each card; new scenario *suggestions* to the Examiner | Approve anything |
| **Verifier** | Re-runs the full ladder on fresh exam draws after an approved fix; issues the Fix Receipt | Everything | `receipts/` | Modify the fix |

**Anti-gaming checks.** These are enforced mechanically, not by trust:

- A fix branch whose diff touches `proving_ground_exam/`, `tests/proving_ground/`, thresholds,
  or `assert_no_lookahead` is auto-rejected.
- Exam specs are sealed by hash, or generated at run time from a runner-held seed.
- Watch for hard-coded dates, market IDs, or scenario fingerprints in engine code. The
  Critic greps for them.
- A fix that improves practice scores but not fresh exam scores is flagged as overfit.
- Keep an **engine-version archive** (Darwin Gödel Machine style): every approved engine
  version, its scoreboard, and its diff. Never overwrite. If a later version regresses, the
  archive shows where, and a rollback is one command.

**Making isolation real, not honor-system.** Local agents can read any file the OS lets them
read, so enforce the "Never" column with tooling. Use the strongest option available and
record which one was used:

1. **Sealed storage outside the fixer's reach.** The Examiner keeps exam specs and the
   exam seed **outside the repository** (e.g., `~/.proving_ground_sealed/`) and commits
   only their hashes. The Runner reads them at run time. Exam results are revealed only
   after grading.
2. **Tool-level deny rules.** Launch each engine-side session with deny rules, for example:
   - Claude Code `permissions.deny` entries such as `Read(~/.proving_ground_sealed/**)`,
     `Read(./proving_ground_exam/**)`, `Edit(./proving_ground_exam/**)` in that session's
     settings
   - Codex CLI's sandbox / writable-roots restrictions

   Launch examiner-side sessions with the mirror-image denies on engine internals.
3. **Separate worktrees.** Fixers work in their own git worktree, from which
   `proving_ground_exam/` has been removed (for example, via sparse checkout).
4. **Audit after the fact.** Harness scripts scan each session's transcript and tool log for
   reads of forbidden paths. A hit invalidates that role's output for the cycle.

**If OS- or tool-level isolation isn't available for a role, independence for that role is
*degraded*.** Disclose it on the scoreboard, in the `AUDIT_REPORT.md` independence record,
and in the Evidence Pack. Don't silently carry on.

**Role manifests.** Every role session ends by writing
`docs/proving_ground/manifests/<cycle>/<role>_ROLE_MANIFEST.md` containing:

- the model and CLI used
- the session ID
- the isolation method in force
- files and directories read
- files written
- external URLs fetched
- the start and end time

The harness cross-checks each manifest against the transcript/tool log where one exists.
A mismatch is an S1 process finding.

---

## 10. The self-improving loop, with the operator in control

"Self-improving" here means the system **comprehensively audits its own runs and the whole
repo, figures out what to improve (both as a whole and part by part), and proposes it in
language the operator can approve in minutes.** Nothing is applied without approval.

### 10.1 The cycle

```
 RUN ladder ──► GRADE (deterministic) ──► AUDIT (2 independent auditors + area chair)
    ▲                                                     │
    │                                                     ▼
 VERIFY on fresh exams ◄── APPLY (approved only) ◄── OPERATOR ◄── CRITIC ◄── PROPOSE (Fix Cards)
    │
    └──► RECEIPT + archive + LESSONS / PLAYBOOK update ──► next cycle (curriculum advances a level when cleared)
```

### 10.2 What "comprehensive audit" covers, every cycle

Auditors check **all** of these, not just the pricing numbers:

1. **Pricing decisions:** the worst nights per level, and why. Trace from the raw signal
   through the feature, SQI, ceiling, P(book), and price to the explanation.
2. **Signals and the moat:** each collector's contribution (ablation), reliability,
   staleness handling, trust between conflicting signals.
3. **Data pipeline:** ingest, vintages, lookahead, schema drift, and the scraper.
4. **Safety:** guardrails, the autonomy ladder, grace-period behavior, pushes under
   degraded health.
5. **Explanations:** do they tell the truth about what moved the price?
6. **Code health:** dead code, duplicated logic, type errors, performance hot spots, test gaps,
   and mutation survivors.
7. **Docs and doctrine drift:** does `docs/rules/` still describe what the code does?
8. **The harness itself:** harness bugs, world realism, exam leakage, and whether any level
   is too easy (hardness verification).
9. **Process:** what slowed this cycle down, fed into `PLAYBOOK.md` (Hermes/Voyager style)
   so the next cycle runs smarter.

Findings are classified by root cause:

- signal missing
- signal misweighted
- wrong trust under conflict
- lookahead
- guardrail gap
- OOD blindness
- explanation mismatch
- code defect
- doc drift
- harness defect

### 10.3 The Fix Card: one per proposed change (`docs/proving_ground/proposals/FIX-###.md`)

Every card uses this exact template, written for a smart non-engineer:

```markdown
# FIX-### — <one-line plain-English title>
**Decision needed:** Approve / Reject / Modify / Ask a question
**Severity:** S1 (could push a wrong price or leak future data) · S2 (costs money) · S3 (quality)
**Estimated value:** $X per season across the 3 homes (range $A–$B), from <which levels/worlds>
**Effort / risk:** small · medium · large  |  risk: low · medium · high
**Budget:** agent time to implement ≈ __ h · ladder re-run wall-clock ≈ __ h · model/API cost ≈ $__ (state $0 if $0)
**Files touched:** `path/one.py`, `config/...yaml` (full list)
**Rollback:** `<exact one-line command>`
**Evidence label:** publishable · internal_only · excluded_from_sales_claims
**Sim-to-real risk:** low · medium · high: could this help the simulated worlds but hurt real
pricing? What real-data evidence (replayed signals, Guesty retrospective, live shadow) supports it?

## In one paragraph
What goes wrong today, in everyday words. No jargon without a definition.

## The night it went wrong (example)
"On Dec 23 of the drought season, Level 4, the engine priced Cloud 9 at $X. Snowpack said
bad, the weather model said fine, and the engine believed the weather model…" + one small chart.

## Where this came from
- Levels / scenarios / worlds where it showed up (run IDs, links)
- Which auditor(s) found it; whether both agreed
- Root-cause class
- Code location(s): `src/...:line`

## What we'd change
Plain-language description, then the exact files and a short diff summary.
What will NOT change (e.g., "guardrails untouched").

## The plan
1. Step … (each step one line)
2. Tests that will prove it works (and which would catch a regression)
3. How it will be verified: full ladder re-run on fresh exams

## What the Critic said
Strongest objection, and the answer to it. Overfitting check result.

## If it goes wrong
Expected side effects, how we'd notice, one-command rollback.
```

### 10.4 The approval queue (`APPROVAL_QUEUE.md`)

The page the operator actually reads. The top shows one sentence on this cycle's result
("Cleared Levels 1–3; failed Level 4 on conflicting snow signals") and the current
scoreboard. Below that is a table sorted by severity, then by dollar value:

| Card | Plain-English title | Severity | $/season | Effort | Critic verdict | Decision |

Rules:

- **Batch related fixes** so the operator makes a few decisions, not dozens.
- Fixes that would change doctrine (`docs/rules/`, locked inputs) are flagged in their
  own section with a ⚠️ marker.
- Record the operator's decision on the card itself (date + choice + any notes).
- `wp-price proving-ground apply` refuses unless that decision is recorded.

### 10.5 After approval

1. The Fixer implements the fix on its own branch (a worktree), with tests.
2. The Verifier re-runs **every** level on fresh exams and writes a **Fix Receipt**:
   before/after scoreboard, dollar impact, any regression, and whether the predicted value
   materialized.
3. If the receipt shows a regression or the value didn't materialize, the fix is reverted
   and the card is reopened with the new evidence.
4. Approved and verified versions go into the engine-version archive. `LESSONS.md` and
   `PLAYBOOK.md` are updated, and the curriculum advances once a level is cleared.

---

## 11. Deliverables

1. **`SCOREBOARD.md`:** levels cleared per engine version, with baseline comparisons.
2. **`APPROVAL_QUEUE.md` + `proposals/` + `receipts/`:** the §10 artifacts.
3. **`AUDIT_REPORT.md`:**
   - coverage matrix
   - mutation scores
   - every failure with a repro command
   - lessons
   - the role and independence record (which model and session did what, and any reduced independence)
   - harness limitations
4. **`EVIDENCE_PACK.md`** (customer-facing, SR 11-7 structure plus plain language):
   1. what the engine does
   2. the ladder, explained like ski-run ratings
   3. what was tested and how, including the independence design and the named biases prevented
   4. data provenance (all free public sources, each labeled real, replayed, or simulated)
   5. results per level and per market, with intervals
   6. moat value per signal
   7. where it lost and what was changed (from the Fix Receipts)
   8. safety record at L5–L6
   9. the live forward-test protocol
   10. reproducibility commands and hashes

   Include one worked night traced from raw SNOTEL/CDOT/forecast inputs all the way to price,
   explanation, and outcome.
   **Prospect-safe language rules.** The generator enforces these, and a Critic session
   reviews the pack against them before it's marked ready:

   - Only `publishable` results appear (rule 10).
   - **"Proven"** appears only for results from the live forward test. Replay and simulation
     results are "tested" or "validated in simulation."
   - Simulated money: "in the simulated world, the engine earned…". Never "would have
     earned," "will earn," or "guaranteed."
   - **No named competitor claims.** "Beats competitors" or any named product (PriceLabs,
     Beyond, Wheelhouse) is allowed only if that exact product was run under license. Our
     heuristics are called **"baseline repricer," "comp-following baseline,"** etc. in
     customer-facing text. "PriceLabs-style" is internal-only wording.
   - Every headline number shows its range or interval, the level, the world count, and
     the market next to it.
   - Failed levels and degraded-independence disclosures are stated on the same page as
     the successes.
   - Lock the plain-language glossary (RevPAN, regret, SNOTEL, level, etc.) in the pack's
     first pages.

5. **Charts** generated from run data, each labeled by data type and evidence label.
6. **Harness tests:**
   - import isolation
   - the time machine refuses `published_at > as_of`
   - the exam-hash check
   - the fix-branch diff guard
   - the same seed gives the same bytes

---

## 12. Phasing and checkpoints

| Phase | Output | Checkpoint |
|-------|--------|-----------|
| 0: MVP (§1A) | L1 + one real L2 season, W1, deterministic runner + scorer, guards, one Fix Card, queue, receipt, Evidence Pack stub | **Operator reads the Fix Card**; exit criteria met |
| R: Research | `RESEARCH_LOG.md`, `DATA_SOURCES.md`, `DESIGN.md` (levels, revised §5.4 thresholds, roles, isolation method per role, lockbox hash) | **Operator approval** |
| B1: Time machine + replay | Free vintages for SNOTEL, forecasts, ENSO, CDOT, T-100, IEM; replay collectors | Lookahead canaries green |
| B2: Examiner build | Worlds, competitors, baselines, oracle, L1–L6 practice + sealed exams | Import isolation green; **hardness verification passed** (baselines fail L5–L6) |
| B3: Grader + guards | Scoring, scoreboard, diff guard, exam hashes | Guard tests green |
| B4: Test layers | Property, metamorphic, mutation, fault injection, cassettes | Mutation score reported |
| C1…Cn: Improvement cycles | Run → grade → audit → Fix Cards → **operator approval** → apply → verify → receipt | Each cycle ends with an updated `APPROVAL_QUEUE.md` |
| K: Lockbox | One-shot final exam, run once, with all fixes frozen | Reported as-is |
| P: Publish | `AUDIT_REPORT.md`, `EVIDENCE_PACK.md` | — |

If a free data source turns out to be unavailable, don't invent it. Mark it unavailable,
adjust the level design, add the paid alternative to `SCALE_UP_OPTIONS.md`, and state what
the gap costs the Evidence Pack.

**Operator questions to raise at the Phase R checkpoint** (don't guess at these):

- Which season and market to seal as the lockbox
- Whether Guesty history for all three homes may be used read-only for calibration
- Pass thresholds per level that the operator would be comfortable showing a prospect
- Whether to start the live 2026-27 shadow test now
- Which model families are available for the independent roles (Claude Code, Codex CLI, both)
- Whether the use of Open-Meteo and any other non-commercial-licensed source is acceptable
  for internal testing, and what to substitute before publishing results
