# Dossier 4 — Market-simulator science

Date: 2026-09-29
Access date for web sources: 2026-09-29

## Question

How to run a 1–6 month season in minutes, with shoppers who look like the Winter Park mix, without crowning an engine that only wins inside the toy.

## What is wrong today

`W1_calm` publishes no booking. `W1_discrete_choice` draws one night at a time against one competitor and is not called. Scoring is expected revenue on a straight line (`proving_ground_exam/scoring/demand.py`). The engine cannot learn from a fill it never sees.

## World model chosen

One simulated day at a time.

1. **Arrivals.** A Poisson count per segment. Each shopper draws check-in lead time, length of stay, party size, willingness to pay, and channel from `SIM_PARAMETERS.md`. Season, holidays, snow, access, and a macro index multiply the Poisson mean. This is an agent-based day, not a discrete-event queue of searches. A full search-funnel microsimulation (browse, filter, abandon) is slower and not identified with 47 stays.
2. **Choice.** Multinomial logit with a segment-level price coefficient and a random coefficient (mixed logit) so people in the same segment do not share one slope. Alternatives: our homes that sleep the party and are free for every night of the stay, four competitor agents, and an outside option. Utility uses the **total stay price**, a quality intercept, and a party-fit penalty. Literature precedent: hotel and airline RM simulators use choice sets with an outside option. The classic airline example is PODS (Passenger Origin-Destination Simulator), a booking-class simulator used to test RM against competitor rules. A public description of that role is Belobaba’s MIT PODS notes, summarized in industry writeups; the original PODS code is not open. **UNVERIFIED:** a single canonical URL for the PODS source code. The design idea used here is the published one: simulate arrivals, let them choose, score realized revenue. Hotel own-price elasticities that vary by season and booking horizon are estimated in Vives, Jacob, and Payeras (Tourism Economics, 2019). https://journals.sagepub.com/doi/10.1177/1354816618800643
3. **Inquiries and cancels.** A shopper who picks us becomes a confirmed stay with probability `conversion`, otherwise an inquiry row that does not block the night. Confirmed stays cancel with a daily hazard that falls as the stay approaches (deposits and plans harden). The hazard levels are **assumed, swept**. First-party cancellations are too few (dossier 2).
4. **Competitors.** Four agents, prices visible to the engine only through a noisy scrape (missing listings, multiplicative noise, and an outage flag):
   - Static owner: price fixed at a seasonal constant.
   - Market follower: yesterday’s median of the other agents, lagged one day.
   - Generalized-tool emulator, taken from PriceLabs’ public description, not from their source: a base price, season and day-of-week factors, a holiday lift, a last-minute discount inside 14 days, an orphan discount, and a pace rule that cuts when occupancy is behind. They state that ski season is less price-sensitive than summer and that far-out dates carry a premium because forecasts are noisy. https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/ and part 2: https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-2/ Min-stay: drop 1 night if 10–20% behind the market over 90 days, 2 nights if more than 20% behind; add 0–2 nights for an important holiday when demand is up at least 10%, dampened inside 60 days. https://help.pricelabs.co/portal/en/kb/articles/understanding-min-nights
   - Undercutter: 8% under the lowest other quote.

5. **Engine interface.** The world writes `reservations`, `nightly_inventory`, `comp_snapshots`, and dated `signal_observations`. It does not import `src.bookprob`, `src.compose`, `src.conditions`, or `src.elasticity`. The harness in `src/proving_ground/market_loop.py` calls `generate_recommendations` and copies recommended prices onto available nights.

## Calibration and the anti-flattery rule

Fit arrival **levels** so a `normal` scenario’s booking-window mix, LOS, inquiry ratio, and rough seasonal occupancy fall inside the ranges in `SIM_PARAMETERS.md`. Those ranges come from dossier 1 and the first-party query, widened because n=47. Do not change logit slopes, WTP, or arrival rates after looking at engine regret. Hold out `holiday_shift`, `den_capacity_cut`, `regime_change`, and `pandemic_collapse`.

## Statistics

At least 30 seeds. Common random numbers: shopper attributes and Gumbel shocks depend on `(scenario, seed)` only, not on the policy, so paired differences are on the same shoppers. Bootstrap the paired revenue difference (resample seeds, 95% percentile interval). When many flags are compared, say so: the intervals are not a family-wise guarantee. A win requires the normal-scenario interval to exclude zero **and** no material loss on stress scenarios. That is a gate, not a p-value hunt.

## Speed

A full engine day on the operator DB is about 4.5–4.8 seconds per home over the nights on the calendar (Phase 0). A proving-ground season at daily cadence was about 71 seconds for one toy home before the determinism gate’s extra rebuilds. 15 scenarios × 30 seeds × 180 days × 3 homes does not fit in an hour at that rate. The budget in this design:

- Parallel processes, one fresh SQLite file per job, explicit PCG64 seeds.
- Price every night on days when a lead-time bucket, a neighbor’s availability, a comp scrape, or a signal changes; reuse the previous recommendation otherwise, only after a hash of every `Recommendation` field matches a full reprice on at least three property-days.
- No surrogate engine and no horizon cut unless that proof exists and the hour still fails. Then stop.

## Validation checklist (must be written down before engine ranks are trusted)

- [ ] Same seed, same scoreboard hash, twice.
- [ ] A booked stay creates a `reservations` row and marks every night `booked`. An inquiry does not.
- [ ] Scrape outage writes `scrape_status=failed` rather than deleting the market.
- [ ] On `normal`, the four sim-to-real ranges pass or the miss is documented.
- [ ] Hindsight revenue is at least the engine’s revenue on the same shoppers.
- [ ] `rate_changes` applied Guesty writes stay 0.

## Scenario library

See `proving_ground_exam/scenarios/`. Each file sets snow, access, macro, supply, scrape health, PMS lag, and holiday offsets. Parameters are multipliers on the frozen calibration, not new elasticities chosen to help the engine.

## What to do next

Build the package described above. Keep `W1_calm` on the existing ladder.

## Open questions

- Is 180 days (1 Nov–29 Apr) the right window, or should summer be a second scenario family? Phase 2 uses the winter window. Summer remains a segment share inside calibration for later.
- Operator: any competitor the homes actually lose to, by name, is useful as a quality score. Do not scrape their guest data.
