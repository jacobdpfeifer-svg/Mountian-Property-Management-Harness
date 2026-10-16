# Competitor anchor rule — thesis, evidence, decision (2026-10-16)

Reproduce: `python scripts/anchor_rule_study.py --db <copy of the operator DB> --trials 60` (the published
results used 60 trials per world; the script's default is 120).
Raw tables: [REPORT.md](REPORT.md), [results.json](results.json). Code: `comp_anchor` in
`src/pricing/pace.py`; tests: `tests/test_comp_anchor.py`.

## The defect

The anchor took one `MAX(as_of)` for the night across every comp of every home and every scrape
status, then kept only this home's good quotes from that one day. The scraper writes a row
(good or failed) for every comp each run, so that date is "today", and on real data on
2026-10-16 the anchor was empty for **every** night of all three homes: the four latest scrape
days had no good quote. Over the whole real window it anchored only 22–23% of (home, night, day)
cells. In the Monte Carlo it anchored 27–36% of decisions, with median error 9–19% when it did.

## Measurements on the real scrapes (2026-09-20 .. 2026-10-16)

- 67% of scrape rows failed; four 0-coverage streaks of 3–4 days; never more than 4 of a set's comps
  quoted on one day.
- A comp's quote for a night drifts ~0.8% in 1–2 days, 3–5% in 1–2 weeks, ~9% at 18–21 days.
- Comps in one set differ a lot: median SD of log price 0.41 (Cloud 9), 0.28 (Northwoods).
- Moves arrive as partial waves: on a down-wave about half the comps cut 5–10% and the rest hold.

## Theses tested

| # | Thesis | Verdict | Evidence |
|---|---|---|---|
| 1 | Per-comp latest good quote, own comp set only, beats any one-date rule | **Kept** | Loss 0.05–0.12 vs 0.18–0.23 for the old rule in all 25 worlds |
| 2 | My first proposal: 14-day age cap, 3-comp minimum | **Rejected** | 14 days was worse than 28/42/60 in every world; losing a comp costs more than a stale quote (spread 28–41% ≫ drift ≤9%) |
| 3 | Move stale quotes by a repeat-sales index of the other comps (BLS "cell-relative" imputation) | **Rejected** | Real holdout: imputed error 4.3% vs carry-forward 2.9% (4–7 days, Cloud 9), worse in every gap bucket and home; only helps in an artificial common-shift world |
| 4 | Minimum comps matters less than the cap | **Partly kept** | At low spread N=1 wins slightly; at Cloud 9's spread or with 3% junk quotes N=3–4 wins; N=3 has the lowest worst-case regret |

## Decision

`ANCHOR_MAX_AGE_DAYS = 42`, `ANCHOR_MIN_COMPS = 3` — the rule with the smallest worst-case regret
(0.011 abs log error) across 24 real-fitted worlds × three fallback-error assumptions.

How firm each half is (independent audit, 2026-10-16):
- **"Per-comp, own set, long cap" is firm.** Every world agrees.
- **The minimum of 3 is a hedge, not a finding.** Fixing the fallback error alone, minimax picks N=4 (10%),
  N=2 (20%) or N=1 (30%). N=3 wins only as the worst case over all three, because the fallback's real
  error is unknown. Measure it (own-history price vs realized) and revisit.
- **42 vs 60 days is not identified.** The simulated trials last 45 days and real history is 26 days,
  so any cap ≥ 45 behaves the same. 42 is a conservative choice inside the observed range.
- Summit Haus and Overlook Ridge have identical comp sets, so "every home" means two distinct comp sets.

## Limits — read before relying on it

- 26 days of real history. The cap beyond 21 days is a model extrapolation; re-run monthly.
- The fallback (home's own reference) error is unknown; it was swept 10/20/30%.
- **The scraper, not the rule, is binding.** With N=3 the real last-day replay anchors only 3% of
  Northwoods nights and 38% of Cloud 9's. Raising scrape success (67% failures) is worth more
  than any anchor rule; until then most Northwoods nights price from own history.
- The market simulator scrapes far more kindly (8% missing, no partial outages, one shared comp
  set) than reality, so its boards understate this defect. A degraded-scrape stress world should
  be added to the next calibration (new calibration hash, new experiment).
