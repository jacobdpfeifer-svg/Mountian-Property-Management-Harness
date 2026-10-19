# R1: Airline revenue management, from first principles to the 2026 state of the art

Output: `docs/research/deep_2026-10/R1_airline_rm.md`

## Question

How do airlines price and control inventory? What did each generation of methods add, what does
the 2026 frontier look like, and which pieces transfer to pricing three luxury mountain homes?

## Cover at minimum

1. **History and generations.** American Airlines DINAMO and Sabre after deregulation (People
   Express case). Fare classes and nesting. Littlewood's rule. EMSR-a and EMSR-b. Leg control vs
   network/O&D control, bid-price controls and virtual nesting. Displacement-adjusted revenue.
   Dynamic programming formulations.
2. **Demand forecasting.** Unconstraining or "untruncation" of censored demand (EM, projection
   detruncation). Pickup and booking-curve models (additive and multiplicative). Advanced
   pickup. Forecast error and its revenue impact. Seasonality and special events. **Spill and
   recapture.**
3. **Buy-down and the death of fare fences.** Low-cost carriers and less restricted fare
   structures. Fare adjustment (Fiig, Isler, Hopperstad, Belobaba). Hybrid forecasting and
   Q-forecasting. Willingness-to-pay estimation. What happens when RM assumes independent demand
   but customers buy down. This is directly relevant to an engine that posts one price per
   night.
4. **Overbooking and no-shows**, and the STR analogue: cancellations and refundable vs
   non-refundable rates.
5. **Continuous and dynamic pricing (2015–2026).** IATA NDC. Dynamic offer creation. Continuous
   pricing (class-free). Offer management and ancillaries. Vendors: PROS, Sabre, Amadeus,
   FLYR, Fetcherr, BCG/Lufthansa. ML/RL in airline RM: what is published and what lift was
   claimed.
6. **Competitive inputs.** Fare scraping and competitor fare feeds (ATPCO, Infare/OAG). How
   airlines react to competitor moves. Price matching and the risk of price wars.
7. **Market intelligence feeds.** Search demand (shopping data), bookings on competitor flights,
   events, macro and fuel. **How airlines use leading demand indicators.**
8. **Organizational practice.** Analyst overrides, influences and "user influences", and how much
   lift comes from humans vs the algorithm. Studies of RM system performance measurement (the
   Revenue Opportunity Model).
9. **Measuring RM benefit.** Simulation (PODS, the Passenger Origin-Destination Simulator at MIT).
   A/B testing. Counterfactual evaluation. **Map PODS to our `proving_ground_exam` market
   simulator and say what we should copy.**

## Transfer analysis (required)

Build a table with these columns: method | core assumption | holds for 3 STR homes? | adaptation
needed | expected value for owner net profit | effort. Pay special attention to:

- A booking-curve or pickup forecast plus a bid-price-like threshold per night. Compare it with
  our pace pricing.
- Unconstraining our thin booking history.
- Fare-adjustment ideas applied to the posted-price, single-product setting.
- Length-of-stay and network effects: a 5-night stay is like a multi-leg itinerary, and gap
  nights are like displacement.
- PODS-style simulation for validating our engine.
