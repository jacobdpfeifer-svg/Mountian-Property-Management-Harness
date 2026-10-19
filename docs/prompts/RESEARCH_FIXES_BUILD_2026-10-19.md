# Build out every fix from the 2026-10 deep research pack

Written 2026-10-19. Repo: `~/code/harness` (public GitHub repo, branch `main`). This prompt is
self-contained. Read it in full before you act.

You are the **build orchestrator**. Your job is to turn every finding, fix and recommendation from the
deep research pack into real, tested, durable changes, and to finish the research items that were
left partial. You work in phases, one fix at a time. After every fix you audit what you just did, and an
independent reviewer audits it too. Nothing is skipped and nothing is patched over.

---

## 1. Operator decisions already made (do not re-ask)

1. **Commit the research.** Commit `docs/research/deep_2026-10/` and
   `docs/prompts/DEEP_RESEARCH_2026-10-16/` (plus this prompt) after the Phase 0 cleanup and leak scan.
2. **Fix the remaining code risks now.** That includes the residual risks of commit `d3e8b92`, the
   weather licence problem, and the unvalidated big-snow price uplift.
3. **Replace the booked-rate line** in `docs/prompts/DEEP_RESEARCH_2026-10-16/00_SHARED_CONTEXT.md` (the clause about what December peak
   nights "have booked" at) with **listed** rates.
4. **Run independent validation**, the way `HANDOFF.md` describes it: fresh reviewer agents under
   `V_REVIEW.md`, fixers under `F_FIX.md`, for S1 and for every dossier section changed by the
   2026-10-19 close-out.

Anything not decided here that changes live prices, buys a product, or adds external exposure is an
**operator question**: record it and continue with the rest. Do not guess.

## 2. Hard boundaries (all agents you launch inherit these)

- **No Guesty writes. No live price push. The canary stays inactive.** Do not pass
  `--confirm-live-write`.
- **Public repo.** Never write booked revenue, booked prices, payouts, Guesty ids (24-hex), guest
  names or guest-level fields, or the name of the cold-call PM company or person. Listed (public)
  prices and per-home aggregates are fine.
- **Database.** For analysis, open `data/wp_pricing.db` read-only
  (`file:...?mode=ro&immutable=1`). Schema changes are additive only, go through the repo's
  mechanism (`src/db/schema.sql`, `src/db/__init__.py` `init_db`), are tested on a copy first, and are
  applied to the real DB only after a backup to `~/wp-price-runs/backups/<timestamp>/`.
- **Policy.** Phase 2 changes (signal health, calendars, the SQI curve) are approved for the default
  path. Everything in Phases 4–7 ships as **experimental candidate policies or shadow arms only**,
  never enabled in `config/policies/default.yaml`. Promotion is an operator decision.
- **Simulator.** Follow the isolation rules in `docs/prompts/NEXT_MARKET_SIM.md` (one run at a time,
  lock file, outputs under `~/wp-price-runs/`, never inside iCloud, never tune
  `proving_ground_exam/market/calibration.yaml` from held-out results). Simulated revenue is not
  realized revenue; never call it that.
- **Scraping.** No new aggressive sweeps. Diagnose from stored errors first. At most one supervised
  live scrape run per phase, at the existing politeness settings, after fixture tests pass.
- **Purchases.** Do not buy PriceLabs, AirDNA, DestiMetrics or an Open-Meteo plan.
- **Git.** Work on a branch `research-fixes-2026-10-19` created from current `main`. One commit per
  fix, message in the repo's style, ending with the attribution lines your harness gives you. **Do not
  push or merge** until the operator says so. Never rewrite history.
- Scratch work and downloads go under `/private/tmp/wp_research/build/` (scripts and downloaded data in
  separate directories). Run Python on downloaded data with `-I`.

## 3. Read first, in this order

1. `docs/research/deep_2026-10/AUDIT_2026-10-19.md`: what is done, what is open, and why.
2. `docs/research/deep_2026-10/S1_synthesis.md`, especially §2.2 (code status and residuals),
   §5 (roadmap with "Traces to"), §6 (what not to do) and §7 (build prompts 7.1–7.4).
3. `docs/research/deep_2026-10/reviews/S1_review.md`, sections A and E.
4. `docs/research/deep_2026-10/R6_data_value_ranking.md` Part A.9 (promotion protocol) and Part C
   (fail-safe designs 1–5).
5. `docs/research/deep_2026-10/R1_airline_rm.md` §3.4, §4.4, §9.3–§9.5 and §12.
6. `docs/research/deep_2026-10/R7_winter_park_demand_drivers.md` §2.3, §3.4, §7 and §9.
7. `docs/research/deep_2026-10/R5_catalog.csv` rows A01, A03, X04, W03, W04, C01, C02, C04, Z04.
8. `docs/prompts/DEEP_RESEARCH_2026-10-16/HANDOFF.md` §2 (agent roles, prompt templates, rate-limit
   recovery), `V_REVIEW.md`, `F_FIX.md`, `00_DEPTH_STANDARD.md`.
9. `docs/rules/` (AUTONOMY, COMP_DATA, OPERATIONS, PRICING_DOCTRINE) and `docs/prompts/NEXT_MARKET_SIM.md`.

Then read the code each fix touches before you change it.

## 4. The durability standard ("no duct tape")

A fix is accepted only if all of these hold. Put this checklist in every ledger entry.

1. **Root cause named.** The ledger states the underlying cause, not only the symptom, and the fix
   removes the cause. Example: a keyword match on free text is replaced by classification on the
   feed's structured fields, not by a longer keyword list.
2. **Fails closed.** Missing, stale, malformed or unexpected input produces an explicit
   `unavailable` or neutral result with a reason. It never produces a confident zero, a default that
   looks like data, or a directional price move.
3. **No silent swallowing.** No bare `except`, no `except Exception: pass`, no ignored return codes.
   Errors are typed, logged with context, and surfaced in health receipts.
4. **Data, not hard-coded dates.** Anything that changes each season (holidays, school breaks, pass
   blackouts) is generated from a rule or loaded from a dated, sourced data file, with a test that
   fails when the next season's data is missing or stale.
5. **Tests that would have caught it.** Each fix adds a regression test built from the real payload
   shape that exposed the defect, plus failure-mode tests (empty, HTML, stale, partial, boundary). Run
   the tests against the pre-fix code once to show they fail, then against the fix.
6. **No hidden coupling.** No new magic numbers without a named constant, a comment citing the
   source (dossier section or URL), and a config entry where an operator might need to change it.
7. **Provenance.** Every stored observation carries its source, fetch time and quality.
8. **Docs updated.** The relevant dossier, `S1_synthesis.md` §2.2/§5 status, and any `docs/rules/` file
   that describes the behaviour are updated in the same commit.
9. **Full suite green.** `.venv/bin/python -m pytest -q` passes with no new skips or xfails, and the
   test count does not drop.
10. **Reversible.** Behaviour changes sit behind config where reasonable, and the commit is
    self-contained so it can be reverted alone.

## 5. The per-fix loop (do this for every item in §7)

1. **Design note** in the ledger: root cause, chosen fix, alternatives rejected and why, files touched,
   tests planned, how it fails closed.
2. **Implement** to the durability standard.
3. **Test:** new tests fail on the old code and pass on the new; full suite green.
4. **Self-audit:** walk the 10-point checklist and write the result. Re-read the diff end to end.
   Grep for leftover debugging, TODOs, broad excepts and hard-coded dates.
5. **Independent code audit:** launch a fresh reviewer agent with no build context. Give it the diff,
   the design note, the research rationale (dossier section) and the checklist. Ask it to try to break
   the fix: adversarial inputs, edge cases, concurrency, timezone and DST, idempotency, and whether the
   root cause is actually removed. It writes its findings into the ledger entry.
6. **Fix every finding** or reject it with evidence in the ledger. Re-run the suite.
7. **Commit** (one fix per commit) and mark the ledger row done with the commit hash.

Ledger: `docs/reports/RESEARCH_FIXES_LEDGER_2026-10-19.md`. Create it with one row per item ID from
§7 before you start. Save after every step so a rate-limit stop loses little. If any agent dies on a
session limit, wait for the reset and resume it with SendMessage, telling it what is already on disk
(`HANDOFF.md` §2).

## 6. Order of work

```
Phase 0  Setup, booked-rate replacement, leak scan, commit the research
Phase 1  Independent validation of S1 and the 2026-10-19 dossier changes   (parallel with Phase 2)
Phase 2  Signal health and calendars: close every d3e8b92 residual
Phase 3  Simulator gates: misspecified worlds and owner-net hindsight      (needed before 4–7)
Phase 4  Comp data spine and comp-set coverage
Phase 5  Signals promotion protocol (R6)
Phase 6  Pooled additive pickup shadow arm
Phase 7  Mountain-state and calendar bands; owner-net stay controls; logging; field-test design
Phase 8  Research completion (every partial or not-done review fix)
Phase 9  Final verification, docs, report
```

If Phase 1 changes a roadmap item, update the affected item in §7 before you build it.

## 7. Work items (nothing here is optional)

### Phase 0: setup and hygiene

- **P0.1 Baseline.** Create the branch. Record the test count, `git log -1`, and the current per-home
  anchor coverage (run `src/pricing/pace.py` `comp_anchor` read-only per home for 2026-12-01 to
  2027-03-31; the 2026-10-19 baseline was 8%, 0%, 0% of nights with ≥3 fresh own-set comps) and the
  scrape failure rate (baseline 67.5% of `comp_snapshots` scrape rows).
- **P0.2 Replace the booked-rate line.** In `00_SHARED_CONTEXT.md`, replace the clause stating what December peak
  nights have booked at with the **listed** December peak range. Derive it read-only from public
  listed prices (for example `price_recommendations.listed_price_at_run` for December peak nights, or the
  listings' public calendars), state the source and date, and round to a range. Then grep both
  research folders and the whole working tree for any other booked, sold, realised or payout dollar
  figure and replace it the same way.
- **P0.3 Leak scan.** Grep both research folders and this prompt for 24-hex ids, booked-price
  patterns, guest names and the cold-call company. Report what you find; fix only by redaction to
  listed or aggregate figures.
- **P0.4 Commit the research.** Commit `docs/research/deep_2026-10/`,
  `docs/prompts/DEEP_RESEARCH_2026-10-16/` and this prompt as one commit.

### Phase 1: independent validation (fresh agents, `V_REVIEW.md` then `F_FIX.md`)

Launch reviewer agents with the `HANDOFF.md` §2 reviewer template. Each reviewer must open at least
15 cited URLs including every load-bearing number listed below, run at least 10 of its own searches,
re-derive the arithmetic, re-run the scripts where they exist (`/private/tmp/wp_research/`; if wiped,
re-pull per R7 Appendix B), and check repo claims against the code. Then a fixer applies the review
per `F_FIX.md` with one ledger row per fix. Maximum two cycles; then escalate to the operator.

- **P1.1 S1 full review.** Load-bearing: 0.595 owner share; 67.5% failure and 8/0/0% coverage; 72-day
  winter lead; H4 bound (+0.06 [−0.07, +0.19], ≤4% for a 30% gas rise); 71.7% Nov–Apr; PriceLabs
  $9.99 and 350/15 km; the Inntopia −10.9% and its snow-hangover study; the PriceLabs minimum-stay
  engine; every repo path in §2 and §7.
- **P1.2 R3 body changes** (fixes 1–13, 15–18 applied 2026-10-19): the 3–4% exploration figure from
  `pace_v3_anchor_repair.yaml`; comp-fill endogeneity and identification options; Falk & Scaglione;
  Millard-Ball; SFpark 62% (UCLA brief); RealPage terms; AB 325; HB25-1090.
- **P1.3 R5 body changes:** origin fuel table; snow prior restatement; A03 station 000223; W03→B and
  Z04→A; AirDNA trial wording.
- **P1.4 R7 body changes:** season-level inference table (re-run `rev_checks.py`); comp tier from
  `comp_snapshots`; all-in $2,427/$2,577 arithmetic; H7 priors; snow-hangover correction; lodging-gas
  literature.
- **P1.5 R1 §9.4–§9.5 and §12; R6 reorganisation and sign wording.**

### Phase 2: signal health and calendars (default path; approved)

- **P2.1 Road-closure classification.** `src/signals/extractors/cotrip.py` currently sets
  `berthoud_closed` when the word "closed" appears anywhere in a matching CARS feature, and the live
  feed carries values such as "Right shoulder closed". Classify events from structured fields
  (`eventType`, lane and shoulder impact, the `active` flag, start and end times, direction, route,
  milepoints). Only a full closure of the road segment sets `berthoud_closed`; chain/traction law sets
  `chain_law`; shoulder and single-lane events may raise `access_risk` but not the closure flag.
  Build fixtures from real feed shapes (fetch a sample read-only from
  `api-511x-co.carsprogram.org/events/map-features` and keep only non-sensitive fields).
- **P2.2 Segment window.** The US-40 window is milepost 233–243. OTIS station 000223 on the
  Empire-side approach is at MP 248.7–254.3. Establish the true milepost range for Empire to Winter Park
  (via Berthoud Pass) from CDOT data, cite it, put it in config, and add a fixture for an east-side event
  that never says "Berthoud".
- **P2.3 I-70 segment logic (R5 X04, recommendation R4).** Add I-70 events with segment awareness:
  closures **east** of Empire (Floyd Hill, Idaho Springs) are shared negatives for Winter Park; closures
  **west** of Empire (Georgetown, the tunnel, Vail Pass) are substitution signals. Include dated
  planned-closure notices (e.g. Floyd Hill). Store as experimental signals; do not wire into price.
- **P2.4 Live verification.** Run the collector read-only against the live feed and record a health
  receipt: every run stores `ok` with structured counts or `unavailable` with a reason, never a bare
  zero on a bad payload. Add a scheduled-run health check if the repo has a health-receipt mechanism.
- **P2.5 Weather provider licence.** The Open-Meteo free tier is non-commercial. Move the forecast path
  in `src/signals/collectors/weather.py` to the NWS API (`api.weather.gov`, public data, descriptive
  User-Agent with contact) with correct units end to end. For historical/archive data, use a
  licence-clean source (NOAA/NRCS: SNOTEL is already in `snotel.py`). If a needed field has no
  licence-clean source, disable that field in production, record why, and raise an operator question;
  do not leave a production dependency on the free tier. Keep the m/s handling explicit and tested.
- **P2.6 Snow price curve.** `config/policies/conditions.yaml` still multiplies price by 1.12 at SQI
  1.2 and 1.18 at 1.3. No dossier validated an uplift (R5, R6, R7: snow is a state, not a weekly
  coefficient). Make the curve neutral above 1.0 as well, keep the falsifiability hook, update
  `tests/test_research_defect_fixes.py`, and report the owner-net effect on the proving-ground
  `record_snow` and `normal` worlds (paired seeds).
- **P2.7 Holidays by rule.** Replace hand-typed federal holiday dates in `config/policies/events.yaml`
  with rule-generated windows (MLK = third Monday of January, Presidents Day = third Monday of
  February, Thanksgiving Wednesday–Sunday, Christmas–New Year window) for every season, with the
  window shapes from R7 §2.5. Add a test that fails if the next two seasons are missing.
- **P2.8 School breaks with provenance.** Spring-break and other origin-market breaks (Front Range
  districts; Texas, Kansas, Oklahoma, Nebraska districts per R5 C01/C02) go in a dated data file with a
  source URL and `verified_on` per row, checked against official district sites (R7 marks the Texas
  dates UNVERIFIED). A test fails when the coming season lacks verified rows. Keep signal strengths as
  labelled priors.
- **P2.9 Ikon blackouts.** Store blackouts per season and per product with source URL and
  `verified_on` (2026-27 Session Pass: 26–30 Dec 2026, 16–17 Jan 2027, 13–14 Feb 2027, per the Winter
  Park pass page). Re-check the Ikon Base Pass at Winter Park. Add a staleness test. Record the open
  operator question: which pass product do guests hold?

### Phase 3: simulator gates (prerequisite for Phases 4–7)

- **P3.1 Misspecified worlds.** Add simulator worlds whose demand differs from the engine's own S(p):
  a kinked PODS-style WTP template, a lognormal-in-price family, over-dispersed (gamma-frailty) weekly
  demand, strategic waiters, a matcher competitor, and channel-lag double-booking risk (R1 §9.1–§9.2,
  recommendation R5). Every later gate runs on these, not only on worlds built from the engine's
  assumptions.
- **P3.2 Multi-season closed loop.** Multi-season seeds with burn-in, where the engine learns from its
  own simulated history, to test spiral-down (R1 R4/R5).
- **P3.3 Owner-net hindsight (ROM).** `scoring.hindsight_revenue` is a gross greedy bound. Build an
  owner-net hindsight and report owner-net ROM % per policy (R1 §9.3, review fix 21).
- **P3.4 Acceptance.** Rank stability of existing candidates between the Poisson and over-dispersed
  worlds is reported; no calibration targets tuned on held-out seeds.

### Phase 4: comp data spine and coverage (S1 prompt 7.1)

- **P4.1 Root-cause the 67.5% failure rate.** Group failures from stored errors
  (`comp_scrape_runs.errors`, `comp_snapshots.scrape_status`) by cause and fix the causes in
  `src/scrape/`.
- **P4.2 Persist the calendar.** `_enrich_min_nights` in `src/scrape/__init__.py` calls
  `provider.calendar()` (12 months of per-day `available` and `min_nights`, `providers.py`) and keeps
  only `min_nights`, only on existing rows. Add a per-day calendar store keyed by comp, stay date and
  fetch time, with availability, min-stay, restrictions, source status and payload quality, for every
  day returned.
- **P4.3 Four states.** Distinguish quoted-ok, calendar-unavailable, not-returned-by-sweep and
  fetch-failed. A failure never overwrites an earlier good row and is never recorded as unavailable.
  Re-runs are idempotent.
- **P4.4 Comp-set coverage.** Two homes have no ≥3-comp anchor on any December–March night because
  their own comp sets are thin. Add comps from `comps` that meet the documented criteria (5+ BR, 14+
  sleeps, active, in the valley; `docs/rules/COMP_DATA.md`), each with a written rationale, through the
  existing comp-set mechanism. Confirm the default policy does not use the anchor (pace off) so there
  is no live price change; report before and after coverage per home.
- **P4.5 Booked vs blocked validation (R4 review fix 17).** Run the block-inference logic on our own
  three homes' public calendars and score it against the operator database, reporting only aggregate
  precision, recall and occupancy bias. This sets how much comp fill can be trusted. Comp fill stays
  an endogenous proxy (R3 §10.2); do not use it as booked demand.
- **P4.6 Receipt.** Print a per-home coverage receipt and the new failure rate.

### Phase 5: signals promotion protocol (R6 Part A.9)

- **P5.1 Hit-rate bug.** Fix `hit_rate` in `src/eval/backtest.py`: count only non-zero pairs in the
  denominator and compare the sign of the centred signal with the sign of the residual.
- **P5.2 IC on residuals.** Score signals against pickup residuals at matching lead, not raw levels.
- **P5.3 Season-block evaluation and multiple-testing control.** Implement R6's protocol (season-block
  splits, FDR or reality-check control across the stream screen, n counted in seasons where relevant)
  in `src/signals/promotion.py`. Show with a null Monte Carlo that the false-promotion rate falls from
  the current 27–31% toward the nominal level.

### Phase 6: pooled additive pickup shadow arm (S1 prompt 7.3)

- **P6.1** Additive pickup forecast pooled across homes, neighbouring dates and prior seasons, shrunk
  to a reference curve, net of expected cancellations (Z04 hazard from a prior plus own data).
- **P6.2** Residual-only price input with a tested bound on how far one booking can move price, and a
  neutral fallback on stale or missing data. No second multiplicative market ratio.
- **P6.3** Experimental candidate policy only. Gate: paired seeds on Phase 3 worlds against
  `pace_v3_anchor_repair` and `current_practice`, forecast Brier/MAE by lead on held-out seasons, and
  peak-at-ceiling share.

### Phase 7: mountain state, stay controls, logging, field design

- **P7.1 Mountain-state and calendar bands (S1 roadmap item 4, R6 Designs 3–4, R7 rec 2).** Reference
  booking curves conditioned on the SWE-anomaly tercile, a post-drought timing band (a booking delay,
  not a level cut: R7 §7, Inntopia's post-drought study), origin break blocks, and access windows. Each
  is a band or state with a neutral fallback, never a fitted weekly coefficient. The R7 rule "do not
  cut on behind-pace before mid-December in a low-snow year" is a hypothesis: test it as an arm on
  drought, record-snow, late-opening and shifted-break worlds.
- **P7.2 R1a demand model** for peak-at-ceiling: a smooth finite-WTP family falling above market
  quotes. Diagnostic: share of peak recommendations at the ceiling and reliability of P(book | p) at
  high prices.
- **P7.3 R1b capacity-1 bid price:** backward recursion over daily lead steps; owner-net values
  converted to nightly-rate units through `owner_terms` (0.595 under current fees). Keep the
  management-fee base as an explicit, flagged assumption until the operator confirms it.
- **P7.4 Stay-level displacement:** price a stay as the sum of night bid prices plus orphaned-night
  value; derive min-stay relaxations from it, replacing the flat orphan discount inside the arm. The
  edge is owner-net economics for 14-to-18-guest stays (PriceLabs already prices neighbour-night
  opportunity cost).
- **P7.5 Logging.** `price_recommendations` and `recommendation_outcomes` already store recommended,
  final, listed and booked prices. Populate `shadow_daily` daily, raise `recommendation_outcomes`
  coverage, and add the exploration draw and the approval delay. No guest fields.
- **P7.6 Field-test design (R1 §9.4–§9.5, recommendation R6).** Build the design and analysis code,
  but do not activate it: assignment by check-in week, whole stays assigned by check-in date,
  comp-market primary covariate plus a synthetic-control second estimator, same-week-last-year as a
  secondary covariate, overrides logged by arm, holiday strata, and an A/A test on last season's
  data. Include the power table so nobody expects the field to detect small effects.
- **P7.7 Gates.** R1a and R1b are evaluated separately, each on Phase 3 worlds; stranded orphan nights
  are reported; kill criteria from S1 §5 apply.

### Phase 8: research completion (every partial or not-done fix)

Each item updates its dossier body and its "Response to review" ledger row, to `00_DEPTH_STANDARD.md`.
Launch research agents for these with the `HANDOFF.md` author template, then a reviewer per changed
section.

- **P8.1 R3 fix 14:** Ticketmaster Platinum, NBA/NFL dynamic pricing, Disney park reservations,
  Evolve, Vail investor-day materials, a window-price vs pass-price series.
- **P8.2 R7 fix 4:** a supply-shock instrument for H4 (Kilian or Baumeister–Hamilton shocks, or the
  dated 2026 Hormuz shock) and UMich/real-PCE controls; re-run and report both ways.
- **P8.3 R7 fix 14 and open gaps:** segment shares (GCCTB/Datafy, CSCUSA in-state share, DEN share) or
  explicit UNKNOWN; the 2016–2019 Town of Winter Park lodging reports to extend the H5 series.
- **P8.4 R1 fixes 11, 20, 22:** the Delta Q2-2025 remarks from a transcript or primary report; read the
  open-access primaries S7, S12, S28, S29, S33 and update the depth column; check the §1.7 DP
  statements against Gallego & Topaloglu (S88); give per-row transfer reasoning for §12 priors and
  revisit R1b's effort given its R5 dependency.
- **P8.5 R2 fix 10c:** cite the Koupriouchina thesis or full text for the late-override finding, or
  remove it.
- **P8.6 R5 fixes 7 and 9:** quote the October 2026 STEO for the oil driver; per-A-stream available-n
  table (cross-checked with R6 Part B).
- **P8.7 R6 fixes 7 and 8:** a real search log for the fix pass and the Fiig paper read at source.
- **P8.8 Source gaps flagged in the S1 review:** the Canina, Walsh & Enz full text (1.74 figure and
  segment results) and the Weatherford & Kimes "beyond about 7 days" detail; confirm or withdraw.

### Phase 9: final verification

- **P9.1** Full test suite; an end-to-end dry run of the daily pricing pipeline with no writes,
  confirming default-policy prices change only where Phase 2 intended (show a per-night diff summary).
- **P9.2** Consistency sweep: S1, R6, the README and the audit match the code and the dossiers; update
  S1 §2.2 and §5 status for every item; append a dated section to `AUDIT_2026-10-19.md`.
- **P9.3** Leak scan of everything committed on the branch.
- **P9.4** Ledger complete: every item ID has a commit hash, a self-audit, an independent audit and
  a status. Nothing marked partly without a reason and an operator question.

## 8. Operator questions to collect, not decide

- The management-fee base behind the 0.595 owner share; turn cost; channel mix.
- Which pass product most guests hold.
- Whether to buy the PriceLabs dashboard ($9.99/month) or start an AirDNA/DestiMetrics trial.
- Any field that has no licence-clean weather source (P2.5).
- Promotion of any experimental arm to the default policy.
- Pushing and merging the branch.

## 9. Final report (in chat)

Start with one line naming the audience. Then: what was built, phase by phase, with commit hashes;
test counts before and after; per-home anchor coverage and scrape failure rate before and after;
simulator results for each gated arm on the misspecified worlds; the independent review verdicts and
how each finding was resolved; anything left partly done and why; the operator questions. State
plainly what was verified and what was not.
