# Deep research pack: pricing-science benchmark and highest-value data (2026-10-16)

## Why this exists

On 2026-10-16 the operator made cold calls to Winter Park property managers. The most useful call
was with a local PM company (name kept out of this public repo; see `00_FIELD_NOTES.md`). Their
claims set the agenda for this pack:

1. The big generic pricers (PriceLabs, Beyond, Wheelhouse, etc.) do not collect or use the data
   that actually moves a specific market. They weight the wrong factors.
2. "There are simply too many factors." The hard problem is picking the factors that matter.
3. Airlines and hotels have run sophisticated revenue management (RM) for decades. STR pricing is
   about 10 years old (it grew with Airbnb and VRBO) and is far behind.
4. Winter Park is a middle-class, drive-to market. Gas prices are keeping Front Range (Denver)
   guests from driving up.
5. About 70% of that company's annual revenue comes in the winter months.

Our thesis since day one: **a hyper-specialized mountain-market engine should beat generic
pricers.** This pack turns that thesis into evidence and a build list.

## The questions

- **Q-A.** How do airlines, hotels and other mature RM industries actually optimize price? What do
  they use that we do not? (R1, R2, R3)
- **Q-B.** What exactly do the generic STR pricers do, and where are they weak for a market like
  Winter Park? (R4)
- **Q-C.** What is the full universe of data streams that could move Winter Park lodging demand
  or willingness to pay, including macro, energy and geopolitical streams? (R5, R7)
- **Q-D.** Which streams carry the most value, how do we prove it with thin data, and how do we
  use the winners to the fullest? (R6)
- **Q-E.** Where should we go from here? This means a gap matrix (what we have vs the best
  practice in each industry) and a build roadmap ranked by expected owner net profit. (S1)

## Structure

| File | Agent task | Depends on | Output |
|---|---|---|---|
| `00_SHARED_CONTEXT.md` | Paste above every prompt | none | none |
| `00_DEPTH_STANDARD.md` | Mandatory depth rules + self-audit | none | none |
| `00_FIELD_NOTES.md` | Call notes: hypotheses to test | none | none |
| `R1_AIRLINE_RM.md` | Airline revenue management | none | `docs/research/deep_2026-10/R1_airline_rm.md` |
| `R2_HOTEL_RM.md` | Hotel revenue management | none | `.../R2_hotel_rm.md` |
| `R3_CROSS_INDUSTRY_RM.md` | Ski lifts, car rental, cruise, ticketing, theme parks, rideshare, more | none | `.../R3_cross_industry_rm.md` |
| `R4_STR_PRICER_TEARDOWN.md` | PriceLabs, Beyond, Wheelhouse, etc. | none | `.../R4_str_pricer_teardown.md` |
| `R5_DATA_STREAM_UNIVERSE.md` | Exhaustive data-stream catalog | none | `.../R5_data_stream_universe.md` + `R5_catalog.csv` |
| `R7_WINTER_PARK_DEMAND_DRIVERS.md` | Test the call's claims against data | none | `.../R7_winter_park_demand_drivers.md` |
| `R6_DATA_VALUE_RANKING.md` | Rank streams by value, then design how to use the top ones | R5, R7 | `.../R6_data_value_ranking.md` |
| `S1_SYNTHESIS.md` | Gap matrix + ranked roadmap | all | `.../S1_synthesis.md` |
| `V_REVIEW.md` | Adversarial reviewer, run once per dossier | the dossier | `.../reviews/<id>_review.md` |
| `F_FIX.md` | Author applies the review | the review | dossier edited in place + "Response to review" appendix |
| `HANDOFF.md` | Full state and instructions for a team taking this over | none | none |

## Run order

1. **Wave 1, parallel:** R1, R2, R3, R4, R5, R7.
2. **Review:** run `V_REVIEW.md` on each wave-1 dossier. A dossier that fails the depth standard
   goes back to its author with the review attached. It is not accepted with gaps.
3. **Wave 2:** R6 (needs the R5 catalog and the R7 findings), then review it.
4. **Wave 3:** S1 synthesis, then review it.

## Ground rules (all agents)

- **Research only.** No code changes, no writes to Guesty, no live price changes, no commits.
- **Public repo.** Do not write the names of call participants, booked revenue, Guesty ids or
  guest data into any file under `docs/`. Use the per-home aggregates already in the repo docs.
- Write only under `docs/research/deep_2026-10/`.
