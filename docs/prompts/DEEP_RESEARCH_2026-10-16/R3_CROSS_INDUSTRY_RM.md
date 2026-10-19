# R3: Price optimization across other industries

Output: `docs/research/deep_2026-10/R3_cross_industry_rm.md`

## Question

Besides airlines and hotels, which industries run sophisticated price optimization on perishable,
capacity-constrained, demand-volatile products? What techniques have they developed that STR
pricing could borrow?

## Industries (cover each; go deepest on the starred ones)

- ★ **Ski lift tickets and season passes.** Vail Epic vs Alterra Ikon pass economics.
  Dynamic lift-ticket pricing (Liftopia history, Vail's advance-purchase discounts). Window-rate
  inflation. How pass sales shift lodging demand. What Vail's 10-K and investor-day materials
  say about pricing, yield and the "commitment" strategy. Winter Park is Alterra/Ikon. Pass
  sales are a **leading indicator** published in earnings.
- ★ **Car rental.** Hertz, Avis, Enterprise: fleet as perishable capacity, one-way and
  length-of-rental pricing, and demand surges around events. Mountain airport (DEN) car-rental
  rates as a demand signal.
- ★ **Cruise lines.** Long-lead, high-ticket, group- and family-heavy products. Booking-curve
  management over 12–18 months. "Load and yield" strategy. Price protection. This is the
  closest analogue to luxury multi-night group bookings.
- ★ **Event ticketing and sports.** Ticketmaster Platinum and dynamic pricing. Secondary
  markets as WTP discovery (StubHub, SeatGeek). Qcue and Digonex in MLB, NBA and NFL. Backlash
  and fairness (the Oasis 2024 case).
- **Theme parks.** Disney date-based ticket pricing and park reservations. Six Flags.
- **Rideshare surge.** Uber and Lyft surge economics. Published papers (Cohen et al. on
  consumer surplus, Castillo). Fairness. Lessons on real-time vs posted prices.
- **Retail and e-commerce markdown optimization.** Rue La La (Ferreira, Lee, Simchi-Levi 2016),
  Zara (Caro & Gallien), Amazon. Fashion markdowns as perishable inventory.
- **Golf tee times, restaurants, parking, utilities and electricity peak pricing, freight and
  shipping.** Cover these briefly. Pull only the transferable idea.
- **Vacation-rental managers at scale.** Vacasa, Evolve, Sonder, Airbnb Smart Pricing. What
  their filings and engineering blogs disclose about their pricing models, including the 2015
  Airbnb KDD paper (Ye et al., "Customized Regression Model for Airbnb Dynamic Pricing") and
  later Airbnb and VRBO/Expedia work.

## Cross-cutting techniques to extract

- Learning while earning: bandits, Thompson sampling, and price experimentation under
  incumbent risk (Besbes & Zeevi; den Boer's survey). **Which work with about 100 bookings a
  year?**
- Bayesian hierarchical pooling across products and markets.
- Reference-price effects and fairness constraints.
- Price-presentation effects: drip pricing, all-in fees (FTC 2025 junk-fee rule for short-term
  lodging), charm prices.
- Demand shaping: discounts on low-demand dates, minimum stays, packaging.

## Transfer analysis (required)

Same table format as R1. Also add a section on **ski-industry signals we can ingest**: pass sales
announcements, Alterra/Vail snow and visit reports, and lift-ticket price moves. Give for each:
source, cadence, how far ahead it leads lodging demand, and how to test it.
