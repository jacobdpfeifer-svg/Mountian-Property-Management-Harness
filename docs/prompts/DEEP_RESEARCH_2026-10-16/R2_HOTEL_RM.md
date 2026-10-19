# R2: Hotel and resort revenue management

Output: `docs/research/deep_2026-10/R2_hotel_rm.md`

## Question

How do hotels, resorts and especially **ski-resort lodging** optimize price and inventory? What do
the best systems use that STR pricers lack? What should we adopt?

## Cover at minimum

1. **Foundations.** Marriott's RM history (Bill Marriott and the "demand forecasting" era, the
   One Yield/MORE systems). Hilton and IHG systems. Published lift figures and who reported them.
   Length-of-stay (LOS) controls: min-stay, closed-to-arrival, closed-to-departure.
   **Displacement analysis** for groups. Overbooking.
2. **Forecasting.** Unconstrained demand by arrival date × LOS × rate segment. Pickup models.
   Regrets and denials data (turnaways). Forecasting with very small properties.
3. **Price optimization.** Price elasticity estimation in hotels. Optimal BAR (best available
   rate) setting. Open pricing (independent pricing per channel and segment). Price ladders vs
   continuous pricing. Price consistency and rate parity across OTAs.
4. **Vendor systems, technical depth.** IDeaS (SAS): G3 RMS and its patents. Duetto ("Open
   Pricing", GameChanger). Atomize. FLYR Hospitality. Pace Revenue. RoomPriceGenie. Lighthouse
   (OTA Insight) for rate shopping. Amadeus Demand360 and Agency360 (forward-looking market
   occupancy). CoStar/STR benchmarking (forward STAR). **Say exactly which data inputs each
   uses.**
5. **Forward-looking market data.** Demand360 and **Inntopia DestiMetrics**. DestiMetrics is the
   mountain-destination standard: occupancy-on-the-books and pacing for ski towns, Winter Park
   included or not (verify). How hotels use forward market occupancy vs competitor rates. How
   much each is worth.
6. **Total revenue management.** Revenue per available room (RevPAR) vs gross operating profit
   per available room (GOPPAR) vs net revenue after distribution cost. Channel cost
   optimization. **Map this to our owner-net objective:** cleaning cost per turn, platform fees
   and management fee.
7. **Resort and ski-hotel specifics.** Vail Resorts lodging, Alterra lodging, Intrawest history.
   Destination pricing tied to lift and snow. Holiday-period packaging. Minimum stays at peak.
   Group and wedding blocks.
8. **Human and organizational side.** Revenue managers' overrides, what makes RM fail at
   independents, and evidence on override value.
9. **Evidence of impact.** Academic studies (Cornell CHR, *Cornell Hospitality Quarterly*,
   *JRPM*). RMS adoption lift studies. Critiques.

## Transfer analysis (required)

Same table format as R1. Must address:

- Length-of-stay pricing and gap-night logic for large homes. Exploit vs block 1–2 night orphan
  gaps.
- Forward market occupancy as the **highest-value hotel input**. Is there an STR or mountain
  equivalent we can get (DestiMetrics, AirDNA forward, Key Data, PriceLabs Market Dashboard)?
  At what cost?
- Rate shopping done right: what Lighthouse does that our scraper (67% failure) does not.
- Optimizing on net revenue (GOPPAR-like) vs our owner-net objective.
