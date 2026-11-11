# Q2 — The turn model

**Verdict: CHANGE.** Keep the turn as the unit of work and keep Beta shrinkage, but stop
computing slack one home at a time. Today each turn's slack assumes the whole crew is
standing in that one house. P(ready) never reads capacity, so the model is blind to the
failure it exists to catch: one short-handed crew with several same-day turns. Five slack
buckets are also more than a 3-home operator's data can fill. Two of the five will hold
nothing but their prior, permanently.

## What the code does

- Slack = (next check-in − checkout, compared in UTC so DST is handled) − elapsed − travel
  − weather buffer (`src/ops/turns.py:194-208`). Elapsed = worker-minutes / `crew_size`
  (`src/ops/__init__.py:54-56`).
- P(ready) = (k·prior + on_time)/(k + n) for the turn's slack bucket, with k = 10 and
  priors 0.35/0.70/0.85/0.93/0.97 (`config/policies/operations.yaml:38-47`,
  `src/ops/economics.py:162-174`).
- Outcomes are pooled per bucket across all properties (`economics.py:122-159`).
- Capacity is a separate utilization number per zone (`economics.py:212-237`). It is never
  fed back into slack or P(ready).

## What the numbers come out to (computed from the current profiles)

These come from running `build_turn` on `config/operations/mont_luxe.yaml` as it stands:

| Home | Same-day, dry | + snow ≥15 cm | + chain law | + Berthoud closed | Gap ≥1 night |
|---|---|---|---|---|---|
| summit_haus / overlook_ridge | slack 145 → ≤240 (0.93) | 80 → ≤120 (0.85) | 50 → ≤60 (0.70) | −40 → ≤0 (0.35) | 1585 → top (0.97) |
| cloud_9 | 160 → ≤240 | 100 → ≤120 | 70 → ≤120 | −20 → ≤0 | 1600 → top |

Each home's elapsed time comes out to 175–215 min because 3 workers split 525–645
worker-minutes. But the roster has exactly **one** 3-person crew covering both zones
(`mont_luxe.yaml:63-70`). Suppose all three homes turn on the same day. That crew needs
about 195+20 + 195+20 + 175+25 = **630 min** of sequential work inside a **360-min**
window (10:00–16:00), so at least one home will be late. The model still gives every turn
slack ≥145 and P(ready) ≈ 0.93.

The capacity view for that same day reports northwoods at 102% (critical) and fraser at
48% (ok). The real load is 1890/1260 = **150%**. The code admits to this double count
(`economics.py:187-188`, `shadow.py:182-184`). The manual import makes it worse: it writes
the double-counted roster into `operations_capacity_snapshots`
(`src/ops/sources/manual.py:17-28`), and from then on `capacity_view` treats that row as
an *imported* source (`economics.py:225-230`).

**Does the capacity model double-count multi-zone crews?** Yes, and it is worse than the
note in the code says. The note calls utilization "optimistic". In practice it is
optimistic in one zone and falsely calm in the other, and P(ready) ignores it either way.

## How many turns per bucket a 3-home operator gets (estimate, not measured)

I tried to read real counts from the production reservations table, but access was denied
for PII reasons. The figures below are **assumptions**. A query should replace them.

Assumptions:
- Ski season ≈ 150 nights.
- Large-home winter occupancy ≈ 55–70%, average stay ≈ 3.5–4.5 nights.
- That gives ~20–25 turns per home per season, so **~60–75 turns for 3 homes**.
- Same-day share in peak weeks ≈ 30–45%, so **~20–30 same-day turns per season**.
- About 15–25% of those fall on days with ≥15 cm of snow.

| Bucket | Turns/season, pooled (est.) | Prior weight after one season (k = 10) |
|---|---|---|
| ≤0 | 0–2 (needs a closure, or chain law plus snow) | ≥83% |
| ≤60 | 0–2 | ≥83% |
| ≤120 | 4–7 | 59–71% |
| ≤240 | 15–25 | 29–40% |
| top (gap ≥1 night, or open) | 40–50 | ~17% |

So for a 3-home operator, the two lowest buckets will be the policy author's guess
(0.35/0.70) indefinitely. Those are exactly the buckets that disqualify stays
(`stay.min_p_ready: 0.60`). The lookback is 730 days (`economics.py:128`), and two seasons
does not change that. **k = 10 itself is fine.** It reads as "trust the prior until you've
seen about a season of same-day turns." The problem is having more buckets than evidence,
not the value of k.

The tally also has two data-quality problems:
- **Open-arrival turns are counted in the top bucket.** `bucket_for(None)` returns the last
  bucket (`economics.py:114-115`), and `observed_readiness` doesn't filter out turns with
  no arriving reservation (`economics.py:151-158`). Lateness against a task deadline when
  no guest is coming is noise, and it lands in the 0.97 cell.
- **"Late" means late against the task's `mustFinishBefore`, not the guest's check-in**
  (`src/ops/sources/guesty_tasks.py:91-96`). Operators often set that deadline loosely or
  leave the default. Nothing checks that it matches the next check-in.

## Should outcomes be pooled across properties?

At 3 homes, pooling is the only workable option: per-home n is about 6 same-day turns per
season. But the variance that matters comes from the **crew**, not the house. At 200
homes, a single pooled curve averages good crews with bad ones. Pool per crew (or per
zone), and fall back to the portfolio pool when n < k. That is still one Beta per cell,
not a hierarchical model.

## Alternatives weighed

| Option | Honest at 3 homes? | Honest at 200? | Verdict |
|---|---|---|---|
| (a1) Crew routing / VRP with time windows | Overkill | Means owning dispatch. VRPTW is NP-hard, and the task tools already own dispatch | **Reject.** Don't build a dispatcher |
| (a2) M/G/c capacity view | No | No. Turns arrive in deadline batches (all due 10:00–16:00 on checkout day), not stationary Poisson. The days that matter have ρ ≥ 1, where there is no steady state | **Reject** |
| (b) Rule checklist ("same-day + hot tub + snow = flag") | Yes, and it explains itself | Misses crew overlap, the main failure | **Use as reasons**, not as the model |
| (c) Read the schedule from Breezeway / Turno / Guesty Tasks | Only if the operator uses one | Yes; they already schedule from reservations | **Prefer when present** |
| Current: per-turn slack + Beta by bucket | Mostly prior | Blind to crew contention | **Change** (below) |

What the vendors say about (c):
- Breezeway says it will "automate the heavy workload of scheduling property tasks to
  ensure each turnover is scheduled and completed on time" and lets managers "monitor your
  team's progress … for complete confidence in property readiness".
- Turno's Guesty marketplace listing says it "will retrieve all the listings and
  reservations to ensure every property and turnover get cleanings scheduled" and "will
  let Guesty know about the cleaning statuses".
- Guesty's Tasks API documents `canStartAfter`, `mustFinishBefore`, `assignee`, `status`,
  and `endTime` ("the date and time the task was completed").

None of the pages I could open claims to compute a probability of being ready on time or a
crew-day overload flag. That is unverified either way: Turno's own pages returned 403, and
the field list on its API docs page did not render.

The valuable thing these tools hold is the **assignment**: who does which turn, and when.
The model should read that instead of modelling a crew. Separately, the Guesty reference I
fetched does **not** document `plannedDuration` or `completedAt`, yet the adapter depends
on both (`guesty_tasks.py:34-36`, `:88-89`). The documented completion field is `endTime`.
That needs checking against the live tenant.

## Proposal: the simplest version that stays honest

1. **Crew-day slack (M).**
   - For each crew and service date, sort that day's turns by next check-in (earliest
     deadline first).
   - Walk forward from checkout time, adding elapsed time plus travel for each turn.
   - Each turn's slack = its deadline − its finish time.
   - When a task was imported with an assignee and start time, use that order instead of
     the greedy one.

   This is list scheduling: O(n log n) per crew-day, no solver, and easy to explain ("3rd
   in queue for crew A"). A crew that covers several zones gets counted once, which
   replaces the per-zone sum in `roster_minutes` (`economics.py:179-193`).
2. **Three buckets instead of five (S).**
   - `<0` (prior 0.35), `0–120` (0.80), `>120` (0.95).
   - Add a separate "no arriving guest" class, excluded from both the tally and P(ready).
   - Keep k = 10. Show n next to every P(ready), and print "prior only" when n < k.
3. **Pool per crew, falling back to the portfolio (S).** This depends on (1) assigning
   turns to crews.
4. **Rules as reasons (S).** Keep the weather buffers. Model hot-tub refill and reheat as
   a wall-clock floor that is **not** divided by crew size; today
   `hot_tub_reset_minutes` gets divided by `crew_size` (`__init__.py:43-56`). The actual
   reheat time is unverified and should come from the operator.
5. **Keep snow off the cleaners (S).** Snow removal is often a separate vendor. Don't add
   snow minutes to the cleaning crew's worker-minutes (`__init__.py:50-51`) unless the
   roster says the cleaners shovel.
6. **Clean up the tally (S).** Drop open-arrival turns. Measure lateness against the next
   check-in time, not only against the task deadline.

Rough size: one M plus five S items. No new dependencies.

## Sources

- Breezeway home page, https://www.breezeway.io/. Fetched 2026-10-06; quotes above.
- STR Specialist, Breezeway review, https://strspecialist.com/reviews/breezeway-cleaning-ops-review. Fetched 2026-10-06 ("PMS auto-sync triggers cleaning and inspection schedules automatically when bookings come in"). Third-party, not vendor documentation.
- Guesty Marketplace, Turno, https://www.guesty.com/marketplace-items/turno/. Fetched 2026-10-06.
- Turno, https://turno.com/features/auto-scheduling/. **Returned 403; not verified.**
- Turno External API v2, https://apidocs.turnoverbnb.com/. Fetched 2026-10-06; only the title rendered, so **fields not verified**.
- Guesty Open API, Tasks list, https://open-api-docs.guesty.com/reference/get_tasks-open-api-tasks. Fetched 2026-10-06.
- Breezeway developer portal, https://developer.breezeway.io/. Fetched 2026-10-06. The index lists a Task API; **fields not verified**.
- Wikipedia, Vehicle routing problem, https://en.wikipedia.org/wiki/Vehicle_routing_problem. Fetched 2026-10-06 (VRPTW definition; "the VRP is also NP-hard").
- Wikipedia, M/M/c queue, https://en.wikipedia.org/wiki/M/M/c_queue. Fetched 2026-10-06 (Poisson arrivals; steady state requires ρ < 1).
- The occupancy, stay-length and snow-day shares above are **unsourced estimates**.
