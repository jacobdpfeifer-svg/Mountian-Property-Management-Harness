# R1: Airline revenue management, first principles to the 2026 frontier, and what transfers to three Winter Park homes

Date: 2026-10-16. Access date for every web source below: **2026-10-16** unless stated otherwise.
Author role: pricing-science research (research only; no code, no commits, no Guesty writes).
Scope: the R1 prompt in `docs/prompts/DEEP_RESEARCH_2026-10-16/R1_AIRLINE_RM.md`, held to
`00_DEPTH_STANDARD.md`. Field-note hypotheses H2, H6 and H7 are tested where airline evidence bears on them.

Conventions:
- **[Sn]** is a source number from the bibliography in Section 13. Inline URLs are given at first use.
- **UNVERIFIED** marks a claim I could not confirm from a primary source or abstract.
- **STALE** marks data older than three years (before 2023-10). Most of airline RM's
  foundational evidence is STALE by this definition; it is still the evidence the field runs on, and I say so where it matters.
- **VENDOR** marks a lift number reported by the party that sells the method (conflict of interest).
- "Our engine" means the code at `~/code/harness` `main` (`src/pricing/pace.py`, `src/bookprob`, `src/compose`,
  `src/elasticity`, `src/ceiling`, `src/min_stay`, `src/leakage`, `proving_ground_exam/`).

---

## 0. Executive summary (read this if nothing else)

**Question.** How do airlines price and control inventory, what did each generation add, what is
the 2026 frontier, and what transfers to three luxury Winter Park homes?

**Answer in five lines.**
1. The math under all of airline RM is: **sell a unit now only if its price beats the expected value
   of keeping it** (Littlewood 1972 → EMSR → bid prices → DP). For a posted price, that becomes
   **price = argmax (π(p) − bid price) · P(book | p)**. The textbook special case **price = bid
   price + 1/b** holds only for exponential WTP *and* sparse arrivals per repricing interval
   (continuous-time Poisson; Gallego–van Ryzin 1994; Fiig et al. 2010; Wittman et al. 2018). How much
   of the bid price reaches the posted rate depends on the WTP family and on arrival intensity (§3.4).
   With our owner-net objective (owner share 0.595 of the nightly rate) the bid price must also be
   converted into nightly-rate units.
2. Our engine maximizes `P × P(book | P)` with **no opportunity cost** (M3 is a crude one-step
   stand-in). With capacity 1 per home-night, the exact bid price is a cheap backward recursion over
   lead-time buckets (§4.4). That is the single most transferable airline idea. It does **not** fix
   the "peak always at ceiling" problem: a bid price is ≥ 0 and only pushes price up. That problem
   needs a separate demand-model change (a finite WTP distribution that falls steeply above market
   quotes, R1a), which is measured separately from the recursion (R1b).
3. Multi-night stays are **network RM**: price/accept a stay by Σ bid prices + orphan-gap
   displacement; network control pays mainly at high load (Williamson: 2–4% above ~85% LF) — i.e.
   holiday and peak weeks (§4.4).
4. Airlines learned the hard way that forecasting from your own sales at your own prices
   **spirals down** (Cooper et al. 2006; Belobaba 2004; hybrid forecasting + fare adjustment were
   worth roughly 20–30% combined in PODS against a naive baseline). Our rejected "own-sold blend" is
   the same *risk* (a self-referential reference price), shown only in a 5-seed, one-season screen,
   not a demonstrated multi-season spiral.
   Remedy: unconstrain with a survival model of time-to-booking, and keep pace in the demand
   forecast, not as a price multiplier (§2–3).
5. Measure like airlines do at their best: **PODS-style closed-loop multi-season simulation with
   over-dispersed demand, a hindsight (ROM) score, and a misspecified-world gate**, and field tests
   assigned by check-in block with a comp-market synthetic-control covariate (§9). Be honest about
   power: the expected effects (≤ ~4%) are **not detectable in the field within two seasons** (§9.5),
   so simulation, including misspecified worlds, is the only evidence the R1–R4 changes will get.

**What does not transfer:** EMSR protection levels, LP bid prices (asymptotic in volume),
overbooking, RL/deep RMS, and "continuous pricing" (we already have it; airline gain ≈ 1–2%).

**Hypotheses.** H6 supported: airline RM is decades ahead, but most of its sophistication solves
volume and network problems three homes do not have. H2 plausible: public descriptions of generic
STR pricers show multiplier chains with no unconstraining and gross rather than owner-net objectives
(§11; R4 should verify). One correction from the 2026-10-19 close-out: PriceLabs' dynamic
minimum-stay engine (2023) does weigh a short booking's guaranteed revenue against the lower booking
probability of neighbouring nights and counts check-in costs
(https://hello.pricelabs.co/minimum-stay-recommendation-engine/), so "no opportunity cost" holds for
the nightly price, not for stay rules. H7: the edge is in market-specific demand
forecasting and correct owner economics, not in optimizer sophistication.

**Top recommendations** (§12): R1a finite-WTP demand model; R1b capacity-1 bid-price recursion
(unit-correct, owner-net); R2 stay-level displacement
pricing; R3 pooled additive/survival pace forecast net of cancellations feeding the bid price; R4
unconstraining and no own-price learning loops; R5 PODS-style simulator upgrades; R6 switchback
field design. All magnitudes are priors; most airline evidence is simulation, vendor-reported, or
STALE, and the adversarial pass (§11.1) lowers confidence in every number while leaving the core
mechanism intact.

---

## 1. History and generations of airline RM

### 1.1 Why RM was invented: deregulation and People Express

The US Airline Deregulation Act (1978) let carriers set fares. Low-cost entrant People Express
undercut incumbents on price. In January 1985 American Airlines launched "Ultimate Super Saver"
deep-discount fares across its network, including every People Express route, and could do so
profitably because its new yield-management system let it sell a *controlled fraction* of each
flight at the low fare while protecting seats for late, high-paying passengers. INFORMS' history
of American Airlines' OR group gives this account and quotes Robert Crandall calling yield
management "the single most important technical development in transportation management since
we entered deregulation" [S1: https://www.informs.org/Explore/History-of-O.R.-Excellence/Non-Academic-Institutions/American-Airlines].
People Express' CEO Don Burr's widely quoted retrospective (that the airline was profitable until
American's RM-backed fares arrived) appears in secondary accounts [S2: https://en.wikipedia.org/wiki/Yield_management;
S3: https://theflyingmoose.net/articles/how-american-airlines-weaponised-data]; I could not find the
primary interview, so the exact wording is **UNVERIFIED**. People Express was absorbed by Texas
Air in 1986–87.

**Lesson that transfers:** RM's first commercial win was *not* "charge more". It was **selling
the low price only on inventory that would otherwise go empty, while protecting inventory for
high-WTP late demand.** For a 3-home STR portfolio this is the same tension: discount early
January weekdays that would go empty, never discount Christmas week that will fill.

### 1.2 DINAMO and the first quantified benefit

Smith, Leimkuhler and Darrow, "Yield Management at American Airlines", *Interfaces* 22(1):8–31
(1992) [S4: https://iaorifors.com/paper/7208] describe American's DINAMO (Dynamic Inventory and
Maintenance Optimizer), fully operational in 1988. They decomposed the intractable whole problem
into three sub-problems — **overbooking, discount allocation, traffic (O&D) management** — and
combined the solutions into final inventory levels. The abstract states: "American Airlines
estimates the quantifiable benefit at $1.4 billion over the last three years" and expects over
$500 million per year going forward. **STALE (1992); self-reported by the airline (the authors
were AA employees), so treat as an upper-end, conflict-of-interest number.** For scale, $500M/yr
was on the order of 5% of AA revenue at the time (**UNVERIFIED** ratio; AA revenue ≈ $10–12B in
1990–91 is my recollection, not checked).

**Transfer note:** the decomposition is the important idea, not the dollar figure. Our engine
already decomposes into ceiling, booking probability, pace, min-stay and guardrails. What DINAMO
had that we lack is an explicit **overbooking/cancellation** sub-problem and an explicit
**traffic (multi-night/LOS) management** sub-problem with a displacement cost (Sections 1.6, 4).

### 1.3 Fare classes, nesting, and booking limits

A flight is sold through a ladder of **fare classes** (booking classes, typically up to 26
letters) with different prices and restrictions (advance purchase, Saturday-night stay,
non-refundability). Inventory is controlled with **nested booking limits**: class *j* may sell
up to *b_j* seats, and higher classes can always take seats that lower classes could have taken
(so a high-fare request is never refused while a lower class is open). The **protection level**
*y_j* is the number of seats reserved for classes 1..*j*; the booking limit for class *j+1* is
*C − y_j*. McGill and van Ryzin's survey of forty years of transportation RM research
(*Transportation Science* 33(2):233–256, 1999) [S5: https://business.columbia.edu/sites/default/files-efs/pubfiles/3925/vanryzin_revenue.pdf]
is the canonical map of this literature and is the primary source I read for this section.

### 1.4 Littlewood's rule (1972)

Ken Littlewood (BOAC) gave the first static solution for one leg and two fares *f₁ > f₂*, with
low-fare demand arriving first [S6: https://en.wikipedia.org/wiki/Littlewood%27s_rule; S7 (arXiv
2304.07391, review of bid-price generation without forecasting): https://arxiv.org/pdf/2304.07391].

- **Objective:** maximize expected revenue from *C* seats.
- **Decision rule:** accept a low-fare request while
  `f₂ ≥ f₁ · P(D₁ > y)` where *y* is the number of seats still reserved for high-fare demand *D₁*.
- **Optimal protection level:** `y₁* = F₁⁻¹(1 − f₂/f₁)`; with normal demand,
  `y₁* = μ₁ + σ₁ · Φ⁻¹(1 − f₂/f₁)`.
- **Inputs:** the distribution of *unconstrained* high-fare demand (hence forecasting and
  unconstraining, Section 2).
- **Interpretation:** the marginal seat is worth `f₁ · P(D₁ > y)` if held — the first
  **opportunity cost / bid price** in RM.

Brumelle and McGill (*Operations Research* 41(1):127–137, 1993) proved that, for *n* nested
classes arriving low-to-high, the optimal policy is of fixed-limit form, with conditions that
reduce to Littlewood-type probability statements, and benchmarked Belobaba's EMSR against the
exact solution [S8: https://ideas.repec.org/a/inm/oropre/v41y1993i1p127-137.html].

### 1.5 EMSR-a and EMSR-b (Belobaba 1987, 1989; refined 1990s)

Belobaba's MIT thesis (1987) and "Application of a Probabilistic Decision Model to Airline
Seat Inventory Control", *Operations Research* 37(2):183–197 (1989) [S9: https://ideas.repec.org/a/inm/oropre/v37y1989i2p183-197.html]
introduced **Expected Marginal Seat Revenue** (EMSR). The 1989 paper reports a Western Airlines
implementation (early 1987) in which "a revenue impact test on a sample of actual flights showed
a significant revenue improvement" over judgmental booking limits — the abstract gives no
percentage. **STALE.**

Formulas (fares *r₁ > r₂ > … > r_n*, independent demands *D_k* with mean μ_k, s.d. σ_k)
[S10: https://en.wikipedia.org/wiki/Expected_marginal_seat_revenue; S9]:

- **EMSR-a:** for each higher class *k ≤ j*, a Littlewood protection against class *j+1*:
  `P(D_k > y_k^{j+1}) = r_{j+1}/r_k`; then `y_j = Σ_{k≤j} y_k^{j+1}`. It ignores that pooled
  demand is less variable than the sum of its parts, so it over-protects.
- **EMSR-b:** aggregate classes 1..*j* into one virtual class with demand `S_j = Σ_{k≤j} D_k`
  and demand-weighted fare `r̄_j = Σ r_k μ_k / Σ μ_k`; protect `y_j = F_{S_j}⁻¹(1 − r_{j+1}/r̄_j)`;
  with normal demand `y_j = Σμ_k + Φ⁻¹(1 − r_{j+1}/r̄_j)·sqrt(Σσ_k²)`.
- **Performance:** EMSR-b is reported to stay within about 0.5% of optimal in Belobaba's tests,
  EMSR-a can lose more than 1.5% (as summarized in S10; I did not read the underlying tests:
  **UNVERIFIED** beyond that summary).

**Why it matters to us:** EMSR is a *quantity* control for many units of one product. We have
one unit per home per night. Protection levels on a capacity of 1 collapse to a single
yes/no: "is the expected value of waiting for a later, higher-paying guest greater than the price
on the table?" That is exactly a **bid price** (Section 1.6) and exactly what our `M3`
one-step "booking horizon" heuristic tries to approximate.

### 1.6 Leg control → O&D (network) control: virtual nesting, DAVN, bid prices

Leg-level control maximizes each flight leg, not the network: a connecting passenger may pay
less than the sum of two local passengers she displaces. McGill & van Ryzin [S5, §4.2.3–4.2.4]
describe the progression:

1. **Virtual nesting / indexing** (Belobaba 1987, Smith & Penn 1988, Williamson 1988/1992,
   Vinod 1989/1995): map every origin–destination–fare (ODF) to a *virtual* bucket on each leg by
   its *network value* rather than its fare class, then run leg EMSR on the virtual buckets.
2. **Displacement-adjusted virtual nesting (DAVN):** the value used for indexing is
   `fare − Σ(displacement cost of the other legs used)`, with displacement costs taken as dual
   prices from a deterministic network LP. Simulation studies "agree in the finding that the use
   of dual prices dominates the other methods" [S5].
3. **Bid-price control:** replace all limits with one number per leg, π_l. Accept itinerary *i*
   iff `fare_i ≥ Σ_{l ∈ i} π_l`. The deterministic LP is
   `max Σ_i f_i x_i  s.t.  Σ_{i∋l} x_i ≤ C_l,  0 ≤ x_i ≤ E[D_i]`, and π_l are the duals of the
   capacity constraints. McGill & van Ryzin call its advantage "very convincing — it replaces
   multiple booking limits and complex nesting schemes with a single bid-price value for each
   flight leg and a simple rule" [S5].

Talluri & van Ryzin (*Management Science* 44(11):1577–1593, 1998) proved bid-price control is
**not optimal in general**, but is **asymptotically optimal when capacities and sales volumes are
large**, provided the right bid prices are used; optimal bid prices can be constant over time
even with nonstationary demand and need not be unique
[S11: https://ideas.repec.org/a/inm/ormnsc/v44y1998i11-part-1p1577-1593.html].
**Transfer warning:** our capacity is 1 per home-night and our volume is ~100 reservations total.
We are at the opposite end of the asymptotic regime. Static LP bid prices will be poor; a bid
price for us has to come from a **dynamic** (time- and state-dependent) value of the remaining
inventory, which with capacity 1 is cheap to compute exactly (Section 4.4).

Williamson's MIT thesis (1992) found network control gains are negligible below ~85% average
load factor and on the order of **2–4%** of revenue at higher loads
[S12: https://dspace.mit.edu/handle/1721.1/68123]. **STALE; simulation.** This is directly
relevant: **multi-night displacement only pays when demand is high** — for us, holiday and peak
weekends, not January midweek.

### 1.7 Dynamic programming formulations

The exact single-leg model (Lee & Hersh 1993; Talluri & van Ryzin textbook ch. 2) is a
finite-horizon DP. Divide the booking horizon into periods *t = T…1* small enough that at most one
request arrives; in period *t* a class-*j* request arrives with probability λ_{jt}. With *x*
seats left, value `V_t(x)`:

```
V_t(x) = V_{t-1}(x) + Σ_j λ_jt · max(0, f_j − ΔV_{t-1}(x)),   ΔV_{t-1}(x) = V_{t-1}(x) − V_{t-1}(x−1)
```

Accept class *j* iff `f_j ≥ ΔV_{t-1}(x)`. **ΔV is the exact bid price.** Gallego & van Ryzin
(*Management Science* 40(8):999–1020, 1994) [S13: https://ideas.repec.org/a/inm/ormnsc/v40y1994i8p999-1020.html]
gave the **pricing** version: sell *x* units by a deadline, Poisson demand with price-dependent
intensity λ(p). Optimal price at state (x, t):

```
p*(x,t) = argmax_p  λ(p) · ( p − ΔV(x,t) )
```

They show optimal prices rise with less stock and fall with less time remaining, give a closed
form for exponential demand λ(p) = a·e^{−αp}, and prove that a fixed price is asymptotically
optimal as volume grows. In this **continuous-time** intensity model with exponential demand the
first-order condition gives `p* = ΔV + 1/α`: price = bid price + a constant markup. Fiig et al.
(2010) reach the same "price-elasticity cost" 1/b from the fare-adjustment side (Section 3.3).
The identity is exact only when at most one sale can occur between price changes (arrivals sparse
per repricing interval) and demand is exponential; §3.4 gives the general pass-through, which is
lower for coarse repricing intervals, for increasing-hazard WTP distributions (e.g. lognormal), and
for our linear model. Our capacity-1 inventory makes ΔV computable exactly (Section 4.4). The modern
textbook treatment of these single-resource and finite-horizon pricing models is Gallego &
Topaloglu, *Revenue Management and Pricing Analytics* (Springer, 2019; ch. 1 single resource with
independent demand, ch. 6 dependent demand, ch. 9–10 pricing and finite-horizon dynamic pricing)
[S88: https://www.springer.com/in/book/9781493996049; chapter list only, text not read].

Talluri & van Ryzin's textbook, *The Theory and Practice of Revenue Management* (Kluwer/Springer,
2004; International Series in OR & MS vol. 68) [S14: Talluri, K.T., van Ryzin, G.J. (2004),
ISBN 0-387-24376-3; catalogue record https://bibsonomy.org/bibtex/6c8e140cfa7d9f3fd312df7eb5c46f59]
is the canonical reference for all of 1.4–1.7. I did not have the full text in this session; its
content is cited from memory of the standard formulations above and cross-checked against S5,
S11, S13 (**book page numbers UNVERIFIED**).

---

## 2. Demand forecasting: the input every airline optimizer depends on

### 2.1 Three families of booking forecasts

Weatherford & Kimes, "A comparison of forecasting methods for hotel revenue management",
*International Journal of Forecasting* 19(3):401–415 (2003) [S17: https://ecommons.cornell.edu/bitstream/handle/1813/72130/Kimes30_Comparison_of_Forecasting.pdf; read in full]
classify RM forecasts (after Lee 1990) into:

1. **Historical booking models:** final demand for past stay dates (moving averages, exponential
   smoothing, Holt-Winters, regression on day of week, season, events).
2. **Advanced-booking models:** how the bookings for a *specific future date* build up over time.
   - **Additive (classical pickup):** `F₀ = B_L + mean_pickup(L → 0)`. Bookings on hand at lead *L*
     plus the average number picked up between lead *L* and arrival on comparable completed dates.
   - **Multiplicative (booking curve / pickup ratio):** `F₀ = B_L × mean(B₀/B_L)`.
   - **Advanced pickup (L'Heureux 1986):** the classical pickup computed with *all* data, including
     stay dates that have not yet arrived but have passed the relevant reading days (e.g. a date two
     weeks out has already observed its 120→14 day pickup, so it contributes to that segment's average).
3. **Combined models:** a weighted average of the historical and advanced-booking forecasts, with
   weight shifting toward the advanced-booking forecast as arrival approaches; or regression on both.

**Evidence:** on Choice Hotels data, "pickup methods and regression produced the lowest error,
while the booking curve and combination forecasts produced fairly inaccurate results"; on Marriott
data "exponential smoothing, pickup, and moving average models were the most robust" [S17].
They also summarize Weatherford (1998): in an airline context, **additive methods and regression
out-performed multiplicative methods** [S17]. **STALE (2003, 1998).** They recommend **MAE over
MAPE** for detailed (rate × LOS) forecasts because small cells (expected 0.2, actual 0) make MAPE
explode [S17] — directly applicable to our capacity-1 nights.

**Mapping to our engine.** `src/pricing/pace.py` is a **multiplicative booking-curve** model:
`index = (on_books + 0.05)/(expected + 0.05)` with `expected = final_occupancy(season) × curve_share(lead)`
(or the historical share at that lead once `min_history = 60` snapshots exist), and the
price multiplier is `clip(1 + 0.30·(index − 1), 0.85, 1.25)`. That is a ratio of on-books to an
expected curve — the form the hotel and airline comparisons rank *worst* of the three. With thin
data a ratio is also noisy: if the expected share at 120 days is 0.12 × 0.70 = 0.084 and one extra
night out of 21 portfolio unit-nights books (0.048), the index swings by ~0.36 and the price by
~11% (my arithmetic on the code's constants). An **additive pickup** form (`expected remaining
bookings = mean pickup from L to 0`) degrades more gracefully, and **advanced pickup** would
roughly double the usable observations at short leads during a live season, which is exactly
when our data is thinnest.

### 2.2 Unconstraining (untruncation) of censored demand

Bookings are **censored**: once a class closed (or the plane filled), further demand was not
recorded. Forecasting on raw bookings under-forecasts high-value demand, which lowers protection,
which censors more demand — the seed of spiral-down (Section 3.2). McGill & van Ryzin trace the
practice to Swan's spill formula and Lee's censored-Poisson maximum likelihood [S5 §2.3].
Guo, Xiao & Li, "Unconstraining methods in revenue management systems: research overview and
prospects", *Advances in Operations Research* 2012:270910 [S16: https://emis.muni.cz/journals/HOA/AOR/Volume2012/270910.pdf; read in full]
review 130+ references. Methods, in rising sophistication:

| Method | Mechanism | Notes |
|---|---|---|
| N1/N2/N3 naive | discard censored obs (N1), use them as if uncensored (N2), or impute class mean/percentile (N3) | N2 biases down hardest |
| Booking profile (BP) | assume the *shape* of the booking curve is independent of level; scale the observed partial curve up to full | "sensitive to the point where the censorship begins" [S16] |
| Pickup detruncation (Skwarek) | censored final = bookings at closure + average pickup from closure lead on *unclosed* flights | additive analogue of BP |
| Projection detruncation (Hopperstad, Boeing) | E-step/M-step like EM but uses the **conditional median** above the censoring point, with a tuning parameter τ | "performs similarly to EM" [S16] |
| EM (Salch; Dempster et al.) | E-step: replace each censored obs by E[D \| D ≥ c] under current (μ,σ); M-step: re-estimate (μ,σ); iterate | "most accurate ... though computational intensity is required" [S16] |
| Life table / Kaplan–Meier, censored regression | survival methods | used by van Ryzin & McGill in simulation |

**EM for normal demand (implementable):** given observations `d_i` with flag `c_i` (censored at
`d_i`), start with μ, σ from uncensored data; repeat: for censored i, `z = (d_i − μ)/σ`,
`E[D|D ≥ d_i] = μ + σ·φ(z)/(1 − Φ(z))`, and the second moment correspondingly; set μ, σ to the
sample moments of the completed data; stop when μ changes < 0.1%.

**Evidence of value:** Weatherford & Pölt, *JRPM* 1(3):234–254 (2002) [S15: https://www.doi.org/10.1057/PALGRAVE.RPM.5170027]:
in simulation EM and projection detruncation were most robust; at 60–80% censoring, their
unconstrained mean was 20–80% higher than naive methods; on a major US airline's data, better
unconstraining was associated with **2–12% revenue gains** (abstract). Skwarek's two-airline test:
up to **3.5%**; BP and PD beat N2 by **2–3%** in revenue (Skwarek; Hopperstad), all as reported in
[S16]. Crystal, Ferguson, Higbie & Kapoor (*POM* 2007) found that a lack of unconstraining causes
significant revenue losses on hotel and casino data [S23: https://repository.gatech.edu/entities/publication/9fcfec43-a0f3-4996-ab40-1fd0a93a4e3a].
**STALE; simulation-heavy; the 2–12% is the authors' own estimate from one airline.**

**What censoring looks like for us (capacity 1).** Our censoring is more extreme and differently
shaped than an airline's:

- A home-night that books at lead *L* reveals *only that at least one acceptable request arrived
  by L* at the posted price. Every later would-be guest is unobserved. Demand intensity after the
  first booking is **always** censored.
- A night that never books is censored at lead 0 (no acceptable request at the prices posted).
- Nights blocked by min-stay rules, owner holds, or adjacency (a 2-night hole under a 3-night
  minimum) are censored by **our own controls** — the analogue of a closed fare class.
- Inquiries that did not convert (Guesty inquiry rows) are partial observations of demand that
  *was* there — the analogue of airline "denials"/turnaways, which airlines rarely record.

The natural capacity-1 unconstraining is **survival analysis of time-to-first-booking**: treat
each home-night as a subject entering at the first lead we observe it open, with hazard
`h(L | price ratio, season, DOW, event)` of receiving an acceptable request at lead *L*; booked
nights are events, unsold nights are right-censored at lead 0, blocked nights are censored at the
lead they became unsellable. A discrete-time logistic hazard (one row per home-night per lead
bucket while open) is the same thing as the `pacing_snapshots` table we already collect
(`src/pacing`), and it gives arrival intensities λ(L) for the bid-price recursion in Section 4.4.
Cross-home pooling with a home random effect is mandatory at our n.

**Choice-based unconstraining for the twins and comps.** Vulcano, van Ryzin & Ratliff (Sabre),
"Estimating primary demand for substitutable products from sales transaction data", *Operations
Research* 60(2):313–334 (2012) [S91: https://ideas.repec.org/a/inm/oropre/v60y2012i2p313-334.html;
abstract] combine an MNL choice model with non-homogeneous Poisson arrivals and estimate **primary
(first-choice) demand** — what would have sold had every product been available — by EM, treating
observed sales as an incomplete observation of primary demand; each iteration is closed form and
limit points are stationary points of the likelihood. Our version: products = Summit Haus, Overlook
Ridge, Cloud 9 and the comp set; availability per night comes from our calendar and the scraper's
"checked and unavailable" rows; sales = our bookings (comps' bookings are inferred only as
availability drops). It estimates demand lost when a twin was already booked (recapture, §2.5)
without assuming independence between homes. It needs scraper reliability far above today's ~3%
anchored nights, so it is a second step after the survival model.

### 2.3 Forecast error and its revenue impact

- Lee's MIT thesis (1990, FTL R90-5) Monte Carlo: **each 10% improvement in forecast accuracy →
  0.5–3.0% higher expected revenue** [S18: https://dspace.mit.edu/handle/1721.1/68100]. **STALE;
  simulation; abstract only.**
- Weatherford & Belobaba (*JORS* 53(8):811–821, 2002): demand forecast accuracy matters most; fare
  variability has little effect; some misestimates can even be beneficial to EMSR-type rules
  [S19: https://ideas.repec.org/a/pal/jorsoc/v53y2002i8d10.1057_palgrave.jors.2601357.html].
- Zickus (MIT, PODS) found interactions: the best forecaster depends on the unconstraining method
  and optimizer it is paired with [S16 §(c)] — components cannot be tuned in isolation.

**Transfer:** our forecast is not a demand count but a booking probability. The relevant accuracy
metric is the **Brier score / reliability of P(book by stay | price, lead)** (L1 Brier is already
flagged as worse than baseline in `docs/plans/OVERHAUL_2026-10-14.md` item 4.6). The airline
lesson is to judge the forecaster *with the optimizer attached*, in revenue (here owner-net)
terms, not in isolation.

### 2.4 Seasonality, holidays, special events, outliers

Airline and hotel systems keep separate forecasts (or explicit adjustments) for holidays and events
because "if regular stay nights are used to develop the forecasts for holidays and special events,
the forecasts may be extremely inaccurate" [S17 §3.6]. Rennie, Cleophas, Sykulski & Dost
(*EJOR* 2021; arXiv 1912.05974) [S22: https://arxiv.org/abs/1912.05974] note that state-of-the-art
airline and rail systems still "rely on analyst expertise to identify outlier demand", and propose
**functional-data-analysis outlier detection on booking curves** with extrapolation; in simulation,
detecting outliers and adjusting forecasts promptly "substantially increases revenue", and positive
and negative outliers have asymmetric revenue effects. **No percentage in the abstract.**

**Transfer:** Winter Park has a small number of enormous outlier windows (Christmas–New Year,
MLK, Presidents' Day, spring break weeks; big-snow weekends). Our `config/policies/events.yaml`
and the calibration v2 holiday spans are the "special event" forecasts. What we lack is an
**online outlier test on the pace curve** (is this week's build-up outside the band of comparable
weeks?) that raises a flag rather than silently moving price. With three homes the curve is
discrete; the test must pool the market (comp availability drawdown from `market_snapshots`) not
just our own nights.

### 2.5 Spill and recapture

**Spill** is demand turned away because capacity (or a closed class) was unavailable; **recapture**
is the share of spilled demand that rebooks on another flight of the same airline. Swan (Boeing)
gives spill formulas from a normal demand model and a revision for RM-system effects, and discusses
when recapture matters [S20: https://wctrs-society.com/wp-content/uploads/abstracts/antwerp/V133.pdf;
abstract-level only — the scanned PDF did not extract, so formula details from it are **UNVERIFIED**].
The standard normal spill expression is the loss function: with capacity *C*, demand ~ N(μ,σ),
`E[spill] = σ·[φ(z) − z·(1 − Φ(z))]`, `z = (C − μ)/σ`. MIT course material defines the recapture
rate as the probability a spilled passenger accepts another of the airline's flights (1.0 in a
monopoly) [S21: https://ocw.mit.edu/courses/1-206j-airline-schedule-planning-spring-2003/7439d2a05c04bb846b5ed58b1c74360f_lec5_passenger_mix_2003.pdf; from search summary].

**Transfer (useful):** a party of 14 that finds Summit Haus taken may book Overlook Ridge (twin,
same street) — **recapture within the portfolio**. When one twin is booked for a date, the other
twin's demand rises by (spilled demand × recapture). `MODEL_SPEC.md` M5 handles only the opposite
case (both free → cannibalization discount λ). The airline framing says the twin's bid price
should *rise* when its sibling books, by roughly recapture × the sibling's unmet demand, and that
discounting one twin to fill it while the other is free mainly moves guests between the owner's
two homes (both owned by the same owner per `config/portfolio/mont_luxe.yaml`). Cloud 9 has a
separate owner, so cross-owner recapture is not a portfolio gain for that owner.

---

## 3. Buy-down, the death of fare fences, and what replaced independent-demand RM

### 3.1 The problem

Classic RM (Sections 1.4–1.7) assumes **independent demand by class**: restrictions (Saturday
night stay, 14/21-day advance purchase, non-refundability) "fence" business travellers out of
cheap fares. In the late 1990s–2000s, low-cost carriers and "simplified" fare structures removed
most fences. Belobaba's 2004 MIT ICAT presentation [S25: https://web.mit.edu/airlines/industry_outreach/board_meeting_presentation_files/meeting-nov-2004/Pricing&RM-Belobaba.pdf; read in full]
shows the real Boston–Seattle structure before (Oct 2001: N–Y classes $458–2,262 with Saturday
stay) and after (May 2004: $374–929, Saturday stay gone), and PODS results: compressing the fare
ratio from 5:1 to 3.5:1 and removing the Saturday-night restriction raised load factor from 74.6% to
77.8% but **cut total revenue 15%**, while the revenue contribution of RM controls rose from 5% to
over 8%. His diagnosis: systems "assumed independent fare class demands ... With unrestricted fares,
passengers buy lowest available fare ... Unless demand forecasts are adjusted to reflect potential
sell-up, high-fare demand will be consistently under-forecast. Optimizer then under-protects,
allowing more 'spiral down'" and "Many airlines are currently using manual overrides" [S25].
**STALE (2004), simulation, but the mechanism is the point.**

### 3.2 Spiral-down, formally

Cooper, Homem-de-Mello & Kleywegt, "Models of the spiral-down effect in revenue management",
*Operations Research* 54(5):968–987 (2006) [S26: https://ideas.repec.org/a/inm/oropre/v54y2006i5p968-987.html]
prove conditions under which a forecast–optimize loop that ignores how low-fare availability
suppresses high-fare sales produces **systematically falling protection levels, high-fare sales and
revenue** over repeated flights.

**Our engine faces the same risk (not a demonstrated spiral).** `docs/plans/OVERHAUL_2026-10-14.md`
records the "floor spiral" and that blending the home's own sold prices into the reference was
rejected because "a home sells at what it lists, so its sales are the engine's own prices again"
($332.8k vs $340.7k simulated owner net). That figure comes from a **5-seed, one-season screen**
with no significance shown; a single season cannot exhibit the repeated-flight feedback that
Cooper et al. model. What it does show is the mechanism: **observed demand is endogenous to our own
past prices**, so a reference or elasticity learned only from our own sales is pulled toward
whatever we charged. Testing for an actual spiral needs the multi-season closed-loop simulation in
R5. The airline cure was to model the *choice* process (sell-up / WTP) explicitly rather than
forecast "bookings at the price we happened to post".

A closer warning for `src/elasticity` is Cooper, Homem-de-Mello & Kleywegt, "Learning and pricing
with models that do not explicitly incorporate competition", *Operations Research* 63(1):86–103
(2015) [S90: https://ideas.repec.org/a/inm/oropre/v63y2015i1p86-103.html; abstract]: two sellers
that each fit a demand model in their *own* price only, estimated from their own prices and sales in
a competitive market, can converge to the Nash equilibrium, to the cooperative outcome, or to
"many potential limit points that are neither", depending on initial conditions. MODEL_SPEC M1
(learning β from our own as-of fills while ~280 comps, many on generic pricers, react) is exactly
this setting: the learned β need not converge to the true own-price slope, and where it lands can
depend on the prior. That argues for keeping M1's strong prior (κ = 40), logging comp prices beside
our own in the learning data, and testing M1 against reactive competitors in simulation.

### 3.3 Fare adjustment (Fiig, Isler, Hopperstad, Belobaba 2010) — read in full

Fiig et al., "Optimization of mixed fare structures: theory and applications", *JRPM* 9(1/2):152–170
(2010) [S24: https://amadeus.com/documents/en/research-papers/rpm200918a.pdf] show that a general
discrete-choice demand can be transformed into an **equivalent independent-demand model** so that
existing optimizers (EMSR, DAVN, DP) still work. The **marginal revenue transformation**:

- Order fare products by price. Let `Q_k` be total demand if product *k* is the lowest open,
  `TR_k = f_k Q_k`. Then the **adjusted fare** (marginal revenue) and **adjusted demand** are
  `f'_k = (TR_k − TR_{k−1}) / (Q_k − Q_{k−1})`, `d'_k = Q_k − Q_{k−1}`.
- Fully undifferentiated structure (everyone buys the lowest open fare): with sell-up
  probability `psup_k`, `Q_k = Q_n · psup_k` and `f'_k = (f_k psup_k − f_{k−1} psup_{k−1}) / (psup_k − psup_{k−1})`.
- **Exponential sell-up** `psup_k = exp(−b (f_k − f_n))` on an equally spaced grid (spacing Δ):
  `f'_k = f_k − f_M`, with the **fare modifier** `f_M = Δ·e^{−bΔ}/(1 − e^{−bΔ})`, and as Δ→0,
  **`f_M → 1/b`**. "Because the fare modifier is the cost associated with buy-down, it is also termed
  the price elasticity cost" [S24]. Only products with positive adjusted fare (above the bid price)
  are opened, so `f_M` acts like a floor on the lowest open fare.
- **Hybrid demand** (part product-oriented, part price-oriented): the adjusted fare is a weighted
  mix of unadjusted and adjusted fares, weight `r_k = d_k^prod / (d_k^prod + Q_n(psup_k − psup_{k−1}))`.

**Evidence (PODS, by the method's authors, two of whom were Amadeus employees):** in monopoly
networks, **hybrid forecasting alone added 10–16% revenue**, and moving to full DAVN-MR (fare
adjustment) added **about 16% more**, with load factor falling from 85% to 72–74%. With two
competing airlines, hybrid forecasting gave **10–13%** and fare adjustment a further **9–14%**;
Airline 1's load factor fell from 86% to 65% while the competitor's apparent demand rose 10–20%, and
the authors stress that DAVN-MR "is not a zero-sum game" [S24]. These are **simulation results
against a deliberately weak baseline (standard forecasting in unrestricted fares, where spiral-down
is severe)**; they bound the cost of ignoring buy-down rather than predict lift for an airline that
already handles it. **STALE (2010).** Other MIT PODS theses report hybrid forecasting + fare
adjustment gains of about **2–4%** in more restricted networks and **over 20%** in fully unrestricted
LCC markets (Kayser, MIT S.M. thesis, 2008, "RM methods for multiple fare structure
environments", advisor Belobaba) [S29: https://dspace.mit.edu/handle/1721.1/44681; abstract], and
Cléaz-Savoyen's 2005 MIT thesis ("Airline revenue management methods for less restricted fare
structures"; the abstract gives no percentages) compared Q-forecasting
(modifies the forecaster) with fare adjustment (modifies the optimizer inputs) [S28: https://dspace.mit.edu/handle/1721.1/32439].
Weatherford's "Intelligent aggressiveness: using forecast multipliers, hybrid forecasting, fare
adjustment, and unconstraining methods to increase revenue" (*Decision Sciences* 48(3):391–419,
2017) [S31: https://www.uwyo.edu/business/about-us/directory/weatherford-larry.html; listing only,
abstract not retrieved] continues the line.

**Q-forecasting** (Belobaba & Hopperstad, early 2000s): forecast all price-oriented demand at the
lowest ("Q") fare level, then distribute it to higher classes by estimated sell-up probabilities;
sell-up is estimated by direct observation, forecast prediction, or inverse cumulative methods, and
in one MIT PODS study forecast prediction gave up to **3%** revenue over threshold methods without
sell-up [S28 search summary: https://dspace.mit.edu/handle/1721.1/45800]. **Hybrid forecasting**
splits demand into product-oriented (fenced, "yieldable") and price-oriented ("priceable")
components; it originates with Kallesen & Boyd, "The science of revenue management when
passengers purchase the lowest available fare", *JRPM* 3(2):171–177 (2004)
[S89: https://www.iaorifors.com/paper/63773; abstract].

### 3.4 The posted-price, single-product translation (the key result for us)

Our homes post **one price per night**: the setting is the *fully undifferentiated* fare structure,
in the continuous limit. The Fiig result then says: **charge p only if `p − 1/b ≥ bid price`**, i.e.
`p* = BP + 1/b`, under exponential WTP. This matches Gallego & van Ryzin's continuous-time pricing
with exponential demand (Section 1.7). The general rule, valid for any demand model, is
`p* = argmax_p (π(p) − BP) · q(p)`. Three consequences, each with the caveats the review
(`reviews/R1_review.md`) correctly required:

1. **The posted price should include the opportunity cost of the night.** Today `src/bookprob` +
   `src/compose` maximize `P × p(P)` (or, under pace pricing, owner share × P + fee margin, times
   p(P)) with **zero opportunity cost** except the M3 heuristic. That is correct only on the last
   day. Far out, the optimal price includes the expected value of selling the same night later.

2. **How much of the bid price reaches the posted rate ("pass-through") is a property of the demand
   model, not a constant.** I re-derived it three ways (scratch scripts, numerically on a $10 grid):
   - *Sparse arrivals, any WTP survival S(p) with hazard h(p) = −S'/S:* the FOC is `p − c = 1/h(p)`,
     so **`dp*/dc = 1 / (1 + h'(p)/h(p)²)`**. Exponential WTP (constant hazard) gives 1. A lognormal
     WTP (increasing hazard; median $2,000, σ = 0.35) gave **0.37** numerically. Linear demand gives
     exactly **1/2**: `P* = P_ref(β − 1)/(2β) + c/2` (FOC `(1 − β) + 2βP/P_ref − β·c/P_ref = 0`).
   - *Saturating buckets* `q_k(p) = 1 − exp(−Λ_k S(p))` with exponential S: the FOC gives markup
     `p − c = (e^x − 1)/(b·x)` and **pass-through `1 / (1 + (x·e^x − e^x + 1)/x)` with x = Λ_k·S(p*)**,
     the expected number of guests willing to pay p* within the bucket. Numerically (b = 1/600,
     c: $0 → $600):

     | Λ_k (expected interested parties per bucket) | 0.01 | 0.1 | 0.5 | 1 | 3 | 10 |
     |---|---|---|---|---|---|---|
     | Pass-through of BP to price | 0.99 | 0.87 | 0.59 | 0.44 | 0.27 | 0.17 |

     This matches the reviewer's table. Pass-through is weakest exactly on high-Λ nights (Christmas,
     holiday weeks). **But** the saturation is partly an artefact of holding one price fixed for a
     whole coarse bucket. The engine reprices daily, and with daily steps x is small for most
     home-nights (a few interested parties spread over months), so per-step pass-through returns
     toward the sparse-arrival value of the chosen WTP family. The recursion in §4.4 should therefore
     use **daily** steps (180 steps × price grid is still cheap), not 11 coarse buckets.
   - **Units.** BP is in owner-net dollars; the posted rate is gross nightly. With
     `π(p) = s·p + m` (`owner_terms()`: s = 1 − 0.155 − 0.25 = **0.595**, m = fee margin per night),
     `(π(p) − V)·q(p) = s·(p − (V − m)/s)·q(p)`, so the **rate-unit bid price is (V − m)/s**. A $1 rise
     in owner-net V moves the nightly rate by 1/(2s) ≈ **$0.84** under linear demand and by about
     1/s ≈ **$1.68** under exponential WTP with sparse arrivals (numerically $1.66 at Λ = 0.01, $0.87 at
     Λ = 1). The fee margin m *lowers* the rate-unit bid price: guest fees make an extra booking worth
     more to the owner, so a night is released at a lower nightly rate than a gross-revenue model
     would choose. M3's `C = q·(floor + ceiling)/2` is in **gross rate units**, so the owner-net
     continuation equivalent to M3 is `V = s·C + m`. Any replacement must convert explicitly.

   So the choice between "100% vs 50% pass-through" is not settled by the airline papers; it depends
   on the WTP family (hazard shape), on Λ, and on repricing frequency. That is why R5's
   misspecified-world gate matters.

3. **The bid price does not fix the inelastic-peak degeneracy; it makes it worse.** The 2026-10-14
   audit found peak recommendations at the ceiling 100% of the time because β = −0.65 puts the
   unconstrained optimum (1.27·P_ref) above any ceiling. Adding BP ≥ 0 gives
   `P* = 1.27·P_ref + BP/2`, which moves further above the ceiling. What can fix it is the
   **demand-model change**: replacing the local linear slope with a finite WTP distribution S(p)
   that falls steeply above the market's high quotes (with capacity 1, what matters is whether the
   *best* guest who will arrive before the stay pays p). That change is R1a; the recursion is R1b.
   They must be measured separately: R1a by the share of peak recommendations at the ceiling and by
   Brier/reliability of P(book | p) at high prices; R1b by owner net with R1a held fixed.

4. **Choose a smooth S(p).** The PODS WTP template (Section 9.1),
   `P(WTP ≥ f) = min(1, exp(−ln2·(f − base)/((emult − 1)·base)))`, is **flat (= 1) below base**.
   With base at the comp anchor, the optimum sits on that kink for any small bid price: numerically,
   with base $1,500 and 1/b = $600, p* stayed at exactly $1,500 for BP = $0 and $600 when Λ ≤ 0.5
   (pass-through 0). Used as the engine's S(p), it would pile prices up at the comp anchor. Use a
   smooth family (lognormal or logit in log price, location = quality-adjusted comp anchor) for the
   engine, and keep the kinked PODS form only as one of the simulator's *alternative* worlds.

### 3.5 Where buy-down bites a posted-price STR

"Buy-down" for a single home is **inter-temporal and cross-listing**, not cross-class:

- **Waiting for a discount** (strategic customers): if the engine reliably cuts price inside 14–21
  days (the MODEL_SPEC interim guard forces β ≤ −1.05 for peak nights behind pace inside 21 days;
  PriceLabs-style last-minute discounts do the same), early high-WTP planners who learn this wait.
  This is spiral-down through time. Li, Granados & Netessine, "Are consumers strategic? Structural
  estimation from the air-travel industry", *Management Science* 60 (2014), estimate from posted
  fares and bookings that roughly **5.2–19%** of airline consumers behave strategically (figure from
  the University of Michigan press release; paper abstract read, estimate not checked in the full
  text) [S87: https://pubsonline.informs.org/doi/references/10.1287/mnsc.2013.1860;
  https://news.umich.edu/?p=22497; IDEAS abstract https://ideas.repec.org/a/inm/ormnsc/v60y2014i9p2114-2137.html:
  5.2–19.2%, first–third quartile across markets, *Mgmt Sci* 60(9):2114–2137]. **But** the same
  paper's counterfactuals find that strategic consumers "don't necessarily reduce airline revenue",
  and that committing to non-decreasing prices is more likely to help business markets and **could
  hurt leisure markets** [S87 abstract]. Our guests are leisure groups, so this cuts against a
  blanket "never discount close-in" stance. The French-rail evidence points the other way for that
  market: a stopping-time strategy with 12 *increasing* fares captured nearly all of the gain of full
  dynamic pricing (Table 5 of S86). Net: keep close-in prices at the opportunity-cost rule (BP +
  markup, which itself discounts where remaining demand is low), do **not** add a no-discount rule,
  and model strategic waiters in the simulator (R5) to see which way it cuts for our segments.
- **Twin substitution**: a guest offered both twins buys the cheaper; pricing them independently is
  pricing two "fare classes" of one product. Wittman, Fiig & Belobaba found joint pricing of two
  substitutable flights added **< 1%** over pricing each independently with a choice-aware DPE
  [S37] (Section 5.2) — so M5's simple heuristic is the right level of ambition.
- **Fee-inclusive display**: platforms show all-in totals, so the WTP comparison is on the total
  (already reflected in `all_in_beta` in `pace.py`).

---

## 4. Overbooking, no-shows, cancellations — and the capacity-1 bid price

### 4.1 Airline overbooking

Overbooking was the first RM problem studied (Beckmann 1958; Rothstein 1971, 1985) [S5 §3;
S32: https://pubsonline.informs.org/doi/abs/10.1287/opre.33.2.237]. The static model sets an
authorization level *AU > C* so that the expected marginal revenue of one more booking equals the
expected marginal denied-boarding cost: accept the (AU+1)th booking iff
`f · P(shows ≤ C | AU+1 booked) ≥ DB_cost · P(shows > C | AU+1 booked)`, with show-ups binomial in
bookings. DINAMO treated overbooking as one of its three sub-problems [S4]. The US GAO reports
voluntary plus involuntary denied boardings are "less than 1 percent" of boardings and falling
(2012–2018 DOT data); in 2018 about 43 voluntary and about 1 involuntary per 100,000 boardings
[S33: https://www.gao.gov/products/gao-20-191; product page, Dec 2019]. Talluri & van Ryzin and Gallego & van Ryzin
extend the DP models to cancellations [S13, S14].

### 4.2 Why overbooking does not transfer, and what does

**Overbooking does not transfer.** Walking a 14-person party from a 6-bedroom home at Christmas
has no substitute in Grand County at any price; platform penalties and review damage make the
denied-boarding cost effectively unbounded. Double-booking across Airbnb/VRBO/direct is the STR
failure mode instead, and it is a sync problem (Section 9.2), not an optimization lever.

**What transfers is the cancellation half:**

- **Cancellation-adjusted value of a booking.** A booking made at lead *L* for a peak night with
  cancellation probability *c(L, policy)* is worth roughly
  `E[value] = P·(1 − c) + c·[refund-retained share·P + P(resell | cancel lead)·E[resale price]]`.
  For a large luxury home, resale probability is high when cancellation happens 45+ days out in
  peak and low inside two weeks. The airline lesson is to **forecast net bookings (gross minus
  expected cancellations)** in the pace curve, otherwise a ski week full of refundable bookings
  reads as "ahead of pace" and prices rise just before a wave of cancellations.
- **Refundable vs non-refundable rate plans** are an STR-available fare fence. Evidence: a study of
  about seven million French and UK hotel room postings finds cancellation premia of roughly
  **10–15% of the full price** until two days before arrival [S35: https://www.unibz.it/it/events/137913-sticky-price-for-declining-risk-the-case-of-cancellation-premia-in-the-hotel-industry;
  event abstract only, authors not captured: **UNVERIFIED** detail]. Jia, Jin & Wagman, "Platform as a
  Rule-Maker: Evidence from Airbnb's Cancellation Policies" (NBER w28878, 2021, rev. 2022; not peer
  reviewed), using Airbnb and VRBO listings in 10 US cities, find Airbnb's rule that bookings be fully
  refundable within 48 hours (for check-ins ≥ 14 days out) led to **higher prices and higher
  occupancy** on Airbnb, slower Airbnb listing growth than VRBO, and some hosts shifting to VRBO
  [S34: https://www.nber.org/papers/w28878; abstract]. Flexibility has a demand value. Industry STR cancellation rates of ~11–18% circulate but trace to
  vendor blogs [S82: https://ainora.lt/blog/vacation-rental-cancellation-statistics-2026] —
  **UNVERIFIED**; we should measure our own per-season rate from Guesty aggregates.

### 4.3 STR analogue table

| Airline concept | STR analogue for 3 homes | Engine location |
|---|---|---|
| Overbooking AU > C | None (do not do it) | — |
| No-show rate | Cancellation rate by lead × season × channel × policy | `src/pacing` (net-of-cancel pace), `src/bookprob` |
| Denied-boarding cost | Walk cost ≈ unbounded; sync failures | `src/pms` sync health |
| Refundable vs non-refundable fares | Flexible vs non-refundable rate plans (VRBO/direct; Airbnb has a non-refundable option) | `src/pricing` (two price points), Guesty rate plans |
| Cancellation-aware bid price | Bid price on a booked night = 0, but value of a *refundable* booking < its price | `src/compose` |

### 4.4 The exact capacity-1 bid price (the most implementable airline idea in this dossier)

With one unit per home-night, the Gallego–van Ryzin / Lee–Hersh DP (Section 1.7) collapses to a
scalar backward recursion. Index lead-time steps `k = K, …, 1, 0`. Use **daily** steps matching
the engine's daily repricing (K ≈ 180), not coarse buckets: with coarse buckets one price is held
for weeks, arrivals saturate within the bucket, and pass-through of the bid price collapses on
exactly the high-demand nights (§3.4 item 2). Λ can still be *estimated* on coarse buckets and
spread over days. In step *k* the home-night, if still open at price *p*, books with
probability `q_k(p)` (from the hazard model of Section 2.2: `q_k(p) = 1 − exp(−Λ_k · S(p))`, Λ_k
the expected number of interested parties arriving in bucket *k*, `S(p) = P(WTP ≥ all-in(p))`).
Value of the open night entering bucket *k*:

```
V_0 = 0                                   (unsold at arrival: worth nothing)
V_k = max_p [ q_k(p) · π(p) + (1 − q_k(p)) · V_{k−1} ]
p*_k = argmax_p q_k(p) · ( π(p) − V_{k−1} )      ← bid price BP_k = V_{k−1}
```

where `π(p)` is **owner net** for the night at nightly rate *p* (owner share × p + fee margin per
night − turnover cost share, exactly `owner_terms()` in `pace.py`). **V is in owner-net dollars;**
the equivalent nightly-rate bid price is `(V_{k−1} − m)/s` with s = 0.595 (§3.4 item 2). Properties:

- `BP_k = V_{k−1}` is the **value of waiting**; it falls toward 0 as arrival approaches, so the
  optimal price falls toward the pure markup — the model *derives* last-minute discounting where
  Λ is low and *refuses* it where late demand is strong (Christmas).
- It replaces `MODEL_SPEC.md` M3, whose continuation `C = q · (floor + ceiling)/2` is a one-step,
  price-agnostic guess of `V_{k−1}`. M3 is already a bid price in disguise
  (`p(P)·P + (1 − p(P))·C` is maximized at the same *P* as `p(P)·(P − C)`); the recursion just
  computes C properly. Units: M3's C is a gross nightly-rate value; the owner-net continuation it
  implies is `s·C + m`, and the recursion's `V_{k−1}` replaces that quantity, not C itself.
- It does **not** cure the ceiling-pinning at peak (BP ≥ 0 raises price); that is R1a's job.
- Cost: ~180 daily steps × ~60 price grid points × 3 homes × 180 nights ≈ 5.8M evaluations per
  run — still seconds in NumPy.
- **Identification** comes from pooling: Λ_k by season × DOW-class × event tier, estimated across
  homes, comp-market availability drawdown (`market_snapshots`) and years; `S(p)` from the WTP model
  anchored at the comp quote (Section 3.4). With ~100 reservations this is still prior-dominated —
  but it is a **structured** prior with an explicit time dimension, which `pace_multiplier` lacks.
- **A model-light alternative** for thin data: Eren, Zhang, Rauch, Kumar & Kallesen (PROS),
  "Revenue management without demand forecasting: a data-driven approach for bid price
  generation" (arXiv 2304.07391) [S7: https://arxiv.org/pdf/2304.07391; read] estimate bid prices as
  an **ex-post greedy proxy of marginal opportunity cost** from historical bookings by remaining
  capacity and time to departure, then project them forward; in their simulations it stayed within
  **< 1%** of the DP optimum across settings and was *more* robust than DP when the demand model was
  misspecified (authors are PROS employees; simulation only). For us the analogue is a hindsight
  value per (season, DOW, event tier, lead): what did comparable nights that were still open at this
  lead eventually earn? It is a useful cross-check on the model-based V_k, and a fallback when Λ and
  S(p) disagree.

**Multi-night stays (network RM).** A stay of nights *d…d+n−1* is an itinerary over *n* legs. The
DAVN/bid-price rule: quote the stay at `Σ_{night} BP(night) + markup`, and accept a requested stay
iff its owner-net ≥ `Σ BP(night) + orphan displacement`, where orphan displacement is the bid
price lost on any 1–2 night gap the stay would strand (the gap's own `V` drops to near zero under the
standing min-stay). Weatherford (1995) found an LOS-aware deterministic LP beat leg-based EMSR by
**up to 2.9%** in hotel tests, as summarized by Zhang & Weatherford (*INFORMS J. Computing*, 2017)
[S71: https://danzhang.com/papers/HotelPricing_Final.pdf; read], who model a hotel's multi-night
problem as a network of 30 legs with itineraries up to 12 legs and compare DLP and dynamic-
programming decomposition (DCOMP) heuristics, finding small but significant differences whose
ranking **depends on capacity-to-demand ratio and maximum LOS**. Williamson's finding that network
control pays only at high load factors (2–4% above ~85% LF) [S12] says the same: **LOS
displacement matters on peak and holiday weeks and barely at all in January midweek.**
Our M4 (`stay_value`) and the orphan-gap scanner in `src/leakage` are hand-built versions of this;
the bid-price formulation unifies them and makes the min-stay rule a *consequence* (open a 2-night
stay only if its value ≥ Σ BP + displacement) rather than a policy table.

---

## 5. Continuous and dynamic pricing, offers, and ML (2015–2026)

### 5.1 Definitions: IATA's maturity matrix

Touraine (IATA), "The industry transformation to dynamic offering", *JRPM* (2021)
[S39: https://www.iata.org/contentassets/0688c780d9ad4a4fadb461b479d64e0d/journal_of_revenue_and_pricing_management_2021_touraine.pdf; read]
sets out IATA's Dynamic Offer Maturity Matrix. Price axis: (1) **pre-defined price points with
dynamic availability** (filed fares + RM class availability — classic RM); (2) **pre-defined price
points with dynamic price adjustments** (filed fares, then mark-up/mark-down by "science
optimization algorithms and shopping context"); (3) **dynamic price determination** (a real-time
computed price with no pre-filed fares). Product axis: static items → static bundles (branded
fares) → dynamic choice of pre-defined bundles → fully dynamic bundling. Touraine notes that in
2020 airlines still relied on "26 booking classes", and describes the interim workaround: file
discount codes, compute "the gap between the price quoted ... and the optimal price generated by its
Offer/Revenue Management system (i.e. bid price adjusted by any business rules, shopping context or
willingness to pay algorithm)", and apply the closest discount [S39]. IATA requires a dynamic offer
to be constructed by the airline in real time in response to a shopping request
[S40: https://www.iata.org/contentassets/0688c780d9ad4a4fadb461b479d64e0d/air-white-paper-dynamic-offer-creation.pdf].
NDC is the XML/API standard that makes that request reach the airline.

**Where we sit:** an STR already has level (3) pricing — we post any integer price per night via
Guesty — and the "shopping context" is mostly hidden from us by the platforms (Airbnb shows us
almost nothing about the searcher). Our direct website is the one channel where we *could* see
shopping context (dates searched, party size), the STR analogue of NDC.

### 5.2 Dynamic pricing engines (DPE) layered on RM

Wittman & Belobaba (*JRPM* 2018, "Dynamic pricing mechanisms for the airline industry: a
definitional framework") distinguish assortment optimization, dynamic price adjustment and
continuous pricing [S36: https://dspace.mit.edu/handle/1721.1/122707]. Wittman, Fiig & Belobaba,
"A dynamic pricing engine for multiple substitutable flights", *JRPM* (2018)
[S37: https://amadeus.com/documents/en/research-papers/Wittman_et_al-2018-Journal_of_Revenue_and_Pricing_Management.pdf; read in full]
give the core DPE objective, flight by flight:

```
f*_i = argmax_{f_i} ( f_i − BP_i ) · Prob(i | f_i)
```

where `BP_i` "represents the bid price (marginal cost of capacity)" output by the existing RM
system, and `Prob(i | f_i) = Prob(WTP > f_i)` in the independent version; the joint version
maximizes `Σ_i (f_i − BP_i)·Prob(i | f_1, f_2)` with a Hotelling (locational) choice model for
departure-time preference. PODS results: **5–7%** revenue over traditional RM in a one-airline,
two-flight network, but the joint (substitution-aware) DPE added **< 1%** over pricing each flight
independently, even with perfect knowledge of preferences — "a simple customer choice model was
able to capture most of the revenue gains of dynamic pricing" [S37]. The 5–7% assumes the airline
can segment requests into leisure vs business and knows WTP well; **simulation; authors include an
Amadeus employee.**

**This is the equation our engine should be.** `(π(p) − BP)·P(book | p)` with BP from Section 4.4,
π in owner-net terms, and `P(book | p)` from the WTP/hazard model.

### 5.3 Continuous pricing (class-free)

Lufthansa Group launched NDC "Continuous Pricing" in October 2019 on most European routes,
replacing the fixed fare-bucket price points with "a continuous series of price points" in direct
and NDC channels only; Lufthansa states it does not use personal data and published no revenue
number [S41: https://www.businesstravelnewseurope.com/TMC-Distribution/Lufthansa-launches-NDC-continuous-pricing-for-lower-fares-].
Szymański, Belobaba & Papen (*JRPM* 20(6):669–688, 2021) [S38: https://ideas.repec.org/a/pal/jorapm/v20y2021i6d10.1057_s41272-021-00350-x.html]
find in PODS that continuous pricing "is generally revenue-positive": **up to 2.0%** for a first
mover, **up to 1.2%** when both airlines adopt; gains shrink at lower demand-to-capacity ratios. A
related MIT thesis summarized in search results found gains can reverse when the baseline already
has many fare classes, and that a competitor can erase a first mover's gain (**UNVERIFIED** —
abstract-level). **Implication:** the jump from 26 price points to continuous is worth ~1–2% for an
airline. We already price continuously; **there is no "continuous pricing" lift left for us to
collect.** Our gains must come from better opportunity cost, demand forecasts and LOS handling.

### 5.4 Vendor claims (all VENDOR unless noted)

| Vendor | Claim | Who measured / conflict | Source |
|---|---|---|---|
| PROS (WTP forecasting) | +4.7% revenue on six routes in three markets for an international carrier; prior rules over-allocated low-fare seats | PROS case study; vendor | [S46: https://pros.com/learn/home/global-airline-increases-passenger-revenue-willingness-to-pay-forecasting] |
| PROS (real-time dynamic pricing) | "Up to 3.5% revenue uplift" | event listing; vendor | [S47: https://app.swapcard.com/event/aviation-festival-asia-2025/product/UHJvZHVjdF8xMjM4NDIy] |
| FLYR (Revenue OS, deep learning) | 5–7% revenue uplift, +4% load factor, "10x reduction in forecasting errors"; Virgin Atlantic >10% uplift in *seat ancillary* revenue | FLYR; no named baseline; vendor | [S44: https://flyr.com/resource-hub/delivering-network-wide-revenue-insights/; S45: https://www.globenewswire.com/fr/news-release/2024/09/23/2951096/0/en/Virgin-Atlantic-Turns-to-FLYR-for-Ancillary-Revenue-Management.html] |
| Fetcherr ("Large Market Model", generative AI) | "Fetcherr says its GenAI solution can boost revenue 6-9%"; analysts can overrule | vendor's own claim, reported by Aviation Week (7 Jan 2025); no audit | [S48: https://aviationweek.com/air-transport/airlines-lessors/generative-ai-super-analyst-may-change-how-airlines-set-prices] |
| Delta + Fetcherr | Q2-2025 call (July 2025): AI pricing on about 3% of domestic fares (StockStory: "about 3% of the domestic network"), plan to reach 20% by end-2025; "results are encouraging" while in test | earnings-call remarks as reported by Constellation Research and StockStory; transcript **not retrieved (UNVERIFIED wording)**. Atlanta News First (S50) says 3% of domestic *flights* and attributes the 20% to an advocacy group | [S92: https://www.constellationr.com/insights/news/delta-starting-scale-its-ai-driven-dynamic-pricing-system; https://stockstory.org/us/stocks/nyse/dal/news/earnings-call/5-must-read-analyst-questions-from-deltas-q2-earnings-call; S50] |
| Sabre (Air Price IQ; AirVision Dynamic Availability, Fares Optimizer) | Air Price IQ "up to 3%" airfare revenue uplift (results "vary, depending on price sensitivity"); ML price recommendations from market dynamics, customer context and booking velocity, built on Dynamic Availability; 2018 launch with Etihad and Aegean as first customers | Sabre; vendor | [S93: https://sabre.com/?p=39090; https://www.ttgasia.com/2018/09/11/sabre-launches-new-dynamic-pricing-solutions-for-airlines/] |
| Amadeus | Research papers on fare adjustment, DPEs and RL co-authored with MIT (S24, S37, S38, S42); MIDT-based booking analytics (§7), with Amadeus research claiming 1–3% bottom-line gain from smart MIDT use | vendor-affiliated research; vendor claim | [S24, S37, S94] |
| Lufthansa Group × PROS | 2022: seven network airlines consolidated onto one PROS Revenue Management + Real-Time Dynamic Pricing instance; Jan 2025: PROS Dynamic Ancillary Pricing; Jan 2026: renewal adding Continuous Pricing and Group Sales Optimizer; no revenue figure published | press releases; vendor | [S95: https://www.businesswire.com/news/home/20220712005223/en; https://www.businesswire.com/news/home/20250128177013/en; https://pros.com/news/lufthansa-group-extend-strategic-partnership/] |
| BCG × Lufthansa | **No BCG role in Lufthansa pricing found** in my searches or the reviewer's; the prompt's pairing could not be substantiated | — | — |
| Infare (competitor fare intelligence) | "hundreds of millions" annually from tracking competitor patterns | CEO quote; vendor | [S52: https://www.travolution.com/news/travel-sectors/air/infare-launches-pharos-to-provide-next-generation-revenue-management-for-airlines/] |

**Adversarial note on Delta/Fetcherr:** US senators (Gallego, Blumenthal, Warner) wrote in July
2025 that individualized pricing could push fares toward each customer's "pain point"
[S49: https://www.blumenthal.senate.gov/newsroom/press/release/video-blumenthal-and-colleagues-demand-answers-from-delta-ceo-as-company-moves-toward-ai-price-model-to-set-airfares];
Delta replied it "has never used, is not testing, and does not plan to use" personal-data-based
individualized fares [S50b: https://ajc-ajc-prod.cdn.arcpublishing.com/business/2025/08/delta-counters-ai-pricing-backlash-insists-it-hasnt-ever-used-personal-data];
House members said in November 2025 the answers were insufficient
[S51: https://chuygarcia.house.gov/sites/evo-subsites/chuygarcia.house.gov/files/evo-media-document/letter-to-delta-re-ai-pricing-11.5.25.pdf].
**Lesson:** price on market state (date, lead, inventory, events), never on who the guest is. Our
guest-data boundary already enforces this.

### 5.5 ML and reinforcement learning in airline RM (published evidence)

- Bondoux, Nguyen, Fiig & Acuna-Agost, "Reinforcement learning applied to airline revenue
  management", *JRPM* 19(5):332–348 (2020) [S42: https://ideas.repec.org/a/pal/jorapm/v19y2020i5d10.1057_s41272-020-00228-4.html]:
  a deep-Q RMS that does not need a separate demand forecaster, trained on very large simulated
  booking datasets on GPUs; a 2022 survey classifies it as single-leg DQN vs an RMS baseline. I did
  not retrieve the result numbers (**UNVERIFIED**).
- Shihab, Logemann, Thomas & Wei (arXiv 1902.06824, 2019) [S43: https://arxiv.org/abs/1902.06824]:
  deep Q-learning for seat control with overbooking and cancellations in a toy simulator,
  "nearly close to the expected optimal revenue"; no field test.
- Airline ML forecasting claims (FLYR "10x", PROS shopping-data 8–40% error reduction, Section 7)
  are vendor-reported.
- **Thin-data reality.** RL needs millions of simulated episodes and a trustworthy simulator; its
  published wins are inside the simulator that trained it. Talluri et al. warn that such simulations
  "only test 'within-model' performance" [S69] (Section 9). For three homes, the defensible ML is
  **Bayesian demand learning with exploration inside guardrails** (den Boer's survey of dynamic
  pricing and learning, *Surveys in OR & MS* 20(1):1–18, 2015 [S77: https://research.utwente.nl/en/publications/dynamic-pricing-and-learning-historical-origins-current-research--2/];
  Ferreira, Simchi-Levi & Wang, "Online network revenue management using Thompson sampling",
  *Operations Research* 66(6):1586–1602, 2018 [S76: https://dspace.mit.edu/handle/1721.1/125757]),
  which is what `MODEL_SPEC.md` M1 already sketches.

### 5.6 The closest published analogue: Wyndham vacation rentals

Wang, McGuire, Terbush, Towns & Anderson, "Choice-Based Dynamic Pricing for Vacation Rentals",
*Interfaces* 51(6):450–462 (2021) [S72: https://ideas.repec.org/a/inm/orinte/v51y2021i6p450-462.html]:
a conditional-logit booking model (lead time, availability, property features, competitor
availability, price sensitivity) plus nonlinear price optimization, tested on Wyndham Destinations
rentals for part of 2018: **+3.5% and +5.2% revenue per unit** in two regions. **Authors included
Wyndham/RCI staff (conflict of interest); thousands of units, not three.** Airbnb's own system (Ye
et al., KDD 2018) [S73: https://blog.acolyer.org/2018//03/customized-regression-model-for-airbnb-dynamic-pricing/]
is a booking-probability classifier plus a price regression with a custom loss, because "each
listing is unique" and demand curves are hard to estimate. Observationally, Airbnb Smart Pricing
adopters cut nightly price 5.7% and raised daily revenue 8.6% (Zhang, Mehta, Singh & Srinivasan,
*Marketing Science* 40(5), 2021 [S74: https://pubsonline.informs.org/doi/fpi/10.1287/mksc.2021.1295]);
but adoption stayed low because hosts held pessimistic beliefs, and the authors propose retraining
the tool with host marginal costs because Airbnb does not observe them (Foroughifar & Mehta,
*Marketing Science*, 2024–25 [S75: https://pubsonline.informs.org/doi/abs/10.1287/mksc.2024.0964]).
**That last point is our structural advantage: we know owner economics (channel fee, management
fee, cleaning, turnover cost) and price on owner net; Airbnb's tool does not.**

---

## 6. Competitive inputs: fare feeds, matching, price wars, and the legal line

### 6.1 How airlines see competitors

Airlines buy competitor fare data from fare filings (ATPCO distributes filed fares industry-wide)
and from shopping/scraping services such as Infare, which advertises 1,300+ sources and rules that
flag competitive fares [S52]. Fares are monitored per O&D, per departure, per lead time —
structurally the same as our `src/scrape` market sweep and `comp_snapshots`. Schedule and capacity
data come from providers such as OAG (not researched further here); competitor *bookings* come from
GDS MIDT data (§7). Belobaba's 2004 deck
also flags the **caching** problem: websites store stale availability, so a displayed fare may not
match current RM controls; PODS showed accepting or rejecting such "unwanted" bookings both cut
network revenue by up to ~1.5–2% [S25, slides 15–17]. The STR analogue is **stale comps** (our
42-day max quote age in `ANCHOR_MAX_AGE_DAYS`) and **channel calendar lag** between Guesty, Airbnb
and VRBO.

### 6.2 What matching does to the matcher

Lua, "Matching of lowest fare seat availability in airline revenue management systems" (MIT S.M.
thesis, 2007, advisor Belobaba) [S53: https://dspace.mit.edu/handle/1721.1/42054; abstract; the
earlier URL in this dossier, handle 60708, was the wrong thesis and is corrected here] simulates in
PODS an airline that matches a competitor's lowest-fare seat availability. In a single symmetric
market the **matching** airline "generally obtains lower revenues", "losing as much as 9.2%",
while "the matched airline benefits consistently". In a four-airline mixed-fare network a legacy
carrier matching an LCC loses **3.4–8.5%** while the LCC and two peripheral carriers gain up to
5.3%; with network RM (hybrid forecasting + DAVN) the matching loss is 3.4–5.8% vs 6.2–7.0% with
leg-based EMSRb, and without matching the network system earns 3.0% more than the leg system.
Gorin & Belobaba (*J. Air Transport Mgmt* 10(4):257–268, 2004) showed that after low-fare entry an
incumbent's average fare can rise or fall depending on whether one or both carriers run RM, so
aggregate fare/traffic metrics are poor evidence of intent [S30: https://ideas.repec.org/a/eee/jaitra/v10y2004i4p257-268.html].
Cohen, Jacquillat, Serpa & Benborhoum, "Managing airfares under competition: insights from a field
experiment", *Management Science* 69(10):6076–6108 (2023) [S56: https://ideas.repec.org/a/inm/ormnsc/v69y2023i10p6076-6108.html]:
in a 5,000-itinerary field experiment with an airline, fare ladders that ignored **quality
differences** between competing carriers produced an inefficient price path; incorporating quality
differences gave a smoother, more profitable path. **This is one of very few airline field
experiments; peer reviewed; airline partner unnamed.**

Hortaçsu, Öry & Williams, "Dynamic price competition: theory and evidence from airline markets"
(NBER w30347, 2022; Cowles DP 2341R1, 2023, with Betancourt) find that with competition, dynamic
pricing raises output but lowers welfare relative to uniform pricing because of the strategic role
of competitor scarcity (a "Bertrand scarcity trap"); the 2023 revision reports that a large
airline's pricing heuristics raise revenue 4–5% [S61: https://cowles.yale.edu/sites/default/files/2023-04/d2341r1.pdf;
abstract-level via search summary, full text not read]. Results from monopoly models (most of this
dossier) do not carry over cleanly.

**Transfer to our comp anchor.** `comp_anchor()` takes the median of each comp's latest good quote
and `pace` scales it. Airline evidence says:
1. **Do not match** the lowest comp; anchor on a **quality-adjusted** market level (Cohen et al.).
   Our calibration v2 `value_index` (bedrooms, capacity, quality) is the right idea and should apply
   to the engine's anchor, not just the simulator's shoppers.
2. **Competitor availability is more informative than competitor price** for a capacity-1
   seller: a comp that is *booked* has left the choice set and raises our recapture (Section 2.5).
   Our scraper's `scrape_status` distinguishes "checked and unavailable" — that availability
   drawdown is the STR analogue of watching competitors' load factors and should feed Λ_k.
3. The `price_war` scenario in `proving_ground_exam/scenarios/` is the PODS matching experiment;
   it should report the engine's loss when it follows an undercutter vs when it holds a
   quality-adjusted anchor.

### 6.3 The legal line

- **US v. Airline Tariff Publishing Co. (1992–94):** DOJ alleged airlines used ATPCO fare filings to
  signal and negotiate fare increases ("trial balloons", future-dated fares); a 1994 consent decree
  barred future-effective fares and other signalling devices [S54: https://justice.gov/archive/atr/public/press_releases/1994/211786.htm;
  S55: https://www.govinfo.gov/content/pkg/FR-1994-03-31/html/94-7672.htm].
- **Algorithmic collusion without communication:** Calvano, Calzolari, Denicolò & Pastorello,
  *AER* 110(10):3267–3297 (2020) [S57: https://art.torvergata.it/bitstream/2108/303883/1/aer.20190623.pdf]:
  Q-learning pricers in repeated oligopoly learned supra-competitive prices sustained by finite
  punishment phases.
- **Gibson v. Cendyn (9th Cir., Aug 15 2025):** independent parallel adoption of the same hotel
  pricing software is not by itself a Sherman Act §1 violation; DOJ had filed an amicus for the
  plaintiffs; commentators expect further litigation [S58: https://www.bakermckenzie.com/en/insight/publications/alerts/2025/08/united-states-ninth-circuit-on-algorithmic-pricing].

**For us:** using public listed prices of comps is ordinary competitive intelligence. Never
exchange non-public prices or plans with other Winter Park PMs (relevant after the operator's cold
calls), never adopt a shared pricing service *with* competitors on the understanding that all will
follow it, and keep the engine's comp response unilateral and documented.

---

## 7. Market intelligence and leading demand indicators

Airlines forecast primarily from their own bookings; the newer inputs are:

- **Shopping (search) data.** A PROS/Emirates talk ("Quantifying the performance gain of using
  shopping data in fare pricing") reported forecast-error reductions up to ~40%, which the authors
  said was inflated by a COVID-era test window; pre-COVID ~20%, and ~8% at the most granular level
  [S59: https://pros.com/?p=51189 — page returned 404 on fetch; figures from search summary,
  **UNVERIFIED**; vendor + airline]. Garrow's 2022 Northwestern workshop deck argues shopping data is
  the key extra input post-COVID [S62: https://transportation.northwestern.edu/docs/2022/20220504_garrow-rm-workshop.pdf;
  not read]. ATPCO marketing claims most airlines use under 1% of available market signal (vendor).
- **Competitor bookings (MIDT).** GDS MIDT (Marketing Information Data Tapes) data record bookings made
  through the GDS channel, including competitors' bookings by market and date. Airlines use it to
  read market share and competitor pickup, not only competitor fares. Amadeus research claims a 1–3%
  bottom-line gain from smart MIDT use [S94: https://www.businesstravelnews.com/More-News/Giving-The-Big-Guns-More-Firepower, via the R1 review; vendor claim, not re-opened]. The STR analogue is **comp
  calendar availability drawdown**: the number of matched comps that go from available to
  unavailable for a stay date between scrapes. It is noisier than MIDT, because a host block looks
  like a booking. Our scraper fetches this calendar and does not store it (R4, R6).
- **Academic evidence on what drives airline price paths.** Williams, "The welfare effects of
  dynamic pricing: evidence from airline markets", *Econometrica* 90(2):831–858 (2022)
  [S60: https://www.econometricsociety.org/publications/econometrica/2022/03/01/welfare-effects-dynamic-pricing-evidence-airline-markets],
  estimated on flight-level search and sales data, finds dynamic pricing shifts surplus from late
  (business) to early (leisure) buyers and raises aggregate welfare vs uniform pricing; whether a
  market-level effect is positive depends on whether price moves are driven by **demand shocks** or by
  **changes in demand elasticity** over the booking horizon.
- **COVID broke history.** PROS' COVID task-force notes say "history is no longer a reliable
  predictor of the future", recommended treating short lockdowns as outliers, and that faster
  adaptation distorts next year's seasonality [S83: https://quasi.pros.com/covid-task-force-2-revenue-management-under-lockdown/; vendor].
  Our `pandemic_collapse` and `regime_change` scenarios exist for this reason.
- **Events, macro and fuel.** Airlines handle events as forecast adjustments (Section 2.4) and fuel
  mainly as a cost/capacity input, not a demand signal. Airline RM literature I found gives no
  quantified demand elasticity to fuel prices; the H4 gas-price hypothesis has to be tested on
  I-70/US-40 traffic data (R7), not borrowed from airlines.

**How airlines actually use leading indicators:** as **adjustments to the remaining-demand
forecast** (Λ_k in Section 4.4), with a human or a detector deciding when a deviation is real, not
as direct multipliers on price. Our signals ladder (`config/policies/signals.yaml`: IC ≥ 0.05, hit
rate ≥ 0.52, n ≥ 40 to go active) is the right gate; the airline lesson is to wire activated signals
into the *demand forecast* feeding the bid price, so their effect on price is mediated by inventory
state (a strong-snow signal raises Christmas BP a lot only if Christmas is still open).

**STR "shopping data" we could own:** (1) direct-website date searches and quote requests (party
size, dates) — log them as aggregate counts per stay date; (2) Guesty inquiry rows (already used by
`src/elasticity` for conversion); (3) Airbnb/VRBO listing-view and wishlist counts if exportable
(**UNVERIFIED** availability via Guesty). Each would enter as an experimental signal under the
ladder.

---

## 8. Organizational practice: analysts, overrides, "user influences"

- Airline RM systems expose **influences**: multiplicative or additive adjustments to demand
  forecasts or sell-up, which analysts apply for events, competitor moves or schedule changes, rather
  than overriding final booking limits. Belobaba (2004) observed "many airlines are currently using
  manual overrides" when fences collapsed [S25]. Fetcherr says airline analysts "can always overrule
  the AI" [S48].
- **How much lift comes from humans?** Zeni, "The value of analyst interaction with revenue
  management systems", *JRPM* 2(1) (2003), ran an experiment at US Airways separating the system's
  effect from the analysts' and concluded analyst interaction adds **up to 3%** incremental revenue
  [S65: https://iaorifors.com/paper/63379; abstract-level, **STALE**; the analysts' employer ran the
  study]. Mukhopadhyay, Samaddar & Colville (2007) proposed measuring
  adjusted vs unadjusted forecasts and argued analysts who reliably improve forecasts on critical
  flights generate significantly more revenue (secondary citation; **UNVERIFIED**).
- **Best evidence (hotels, large n):** Koupriouchina, van der Rest & Schwartz (*Tourism Economics*
  29(8):2143–2164, 2023) analysed **20,081,973 forecasts from 1,752 hotels in 232 chains**: more user
  overrides **helped group-segment forecasts and hurt transient forecasts**, and override frequency
  **improved accuracy during special-event periods** [S64: https://ideas.repec.org/a/sae/toueco/v29y2023i8p2143-2164.html].
  Koupriouchina's 2019 Leiden thesis: late adjustments help more than early ones; group forecasts
  benefit more than individual ones [S63: https://openaccess.leidenuniv.nl/handle/1887/80328].
- **Fairness.** Kimes & Wirtz (*JRPM* 2003) and Wirtz & Kimes (2007) find perceived fairness of
  RM practices depends on framing, fences and familiarity; when customers find hotel RM fair they are
  more satisfied and likelier to return [S78: https://ecommons.cornell.edu/entities/publication/db914141-6f90-4631-b2c8-b5696ac85190].

**Transfer:** our guests are mostly *groups* booking around *events* (holidays, ski weeks) — exactly
the segments where human overrides helped in hotel data. Recommendation (R8 below): an operator
**influence** channel (e.g. "a local event on a given weekend, +20% demand", or "two large
corporate inquiries for MLK") that adjusts Λ_k, is logged with author and timestamp, and is scored
afterwards against the no-influence counterfactual — not a free-form price override. The existing
`compose.deference` (nudging around the incumbent listed price under low confidence) is a form of
override; it should be measured the same way.

---

## 9. Measuring RM benefit: PODS, ROM, A/B and counterfactual tests

### 9.1 PODS (Passenger Origin–Destination Simulator)

PODS began at Boeing (Hopperstad) and became the MIT PODS Research Consortium's testbed; member
airlines in 2004 included Continental, Delta, Lufthansa, SAS, Northwest, KLM, Air New Zealand
[S25, slide 3]. Belobaba's 2006 MIT lecture "Introduction to PODS passenger choice model"
[S70: https://ocw.iti.hr/courses/aeronautics-and-astronautics/16-75j-airline-management-spring-2006/lecture-notes/lect6a.pdf; read in full]
specifies its structure:

1. **Repeated samples of a stationary booking process**: "Multiple iterations (samples) of
   pre-departure booking process and departure day ... Initial input values for demands, then
   gradual replacement with direct observations ... 'Burn' first n observations in calculating final
   scores."
2. **Time frames**: the pre-departure period is cut into (16) booking periods; "RM system
   intervention at start of each time frame; bookings arrive randomly during time frame; historical
   data base updated at end of time frame."
3. **Closed loop**: "Previously applied booking limits affect actual passenger loads and, in turn,
   future demand forecasts ... RM system only uses data available from past observations." The RM
   system must forecast from *simulated history it helped create* — which is how PODS exposes
   spiral-down.
4. **Demand inputs**: total daily O-D demand by passenger type; booking curves by type over 16
   periods; **"correlation parameters between passenger types and across booking periods"**
   (demand is over-dispersed and correlated, not independent Poisson).
5. **Passengers**: two types with Gaussian-distributed maximum WTP and "attributed costs"
   (restriction disutilities, path quality, replanning). WTP form:
   `P(pay ≥ f) = min[1, exp(−ln2 · (f − basefare)/((emult − 1)·basefare))]`, basefare = lowest
   (Q) fare for leisure and 2.5 × Q for business, emult = 1.2 leisure, 3 business. A passenger screens
   out paths above WTP and picks the lowest total generalized cost (fare + restriction + path quality
   + replanning disutilities).
6. **Competition**: multiple airlines, each with its own RM method, in the same markets.

### 9.2 PODS → `proving_ground_exam`: what we already have and what to copy

| PODS feature | `proving_ground_exam` today (read from code) | Copy? |
|---|---|---|
| Passenger choice among competitors + outside option | Mixed logit on all-in total stay price, quality, party fit, 4 competitor agents, outside option (`market/choice.py`, dossier 04) | Have it (richer than PODS' screening rule) |
| WTP distribution by segment | Segment WTP multipliers by season (calibration v2) | Have it; add PODS-style **explicit WTP cap screen** so `S(p)` is testable against the engine's model |
| Booking curves by segment | Lead buckets per segment and season (`market/shoppers.py`) | Have it |
| **Over-dispersed, correlated demand** ("k-factors", correlation across periods) | Daily `rng.poisson(mean)` per segment, modulated by scenario snow/access/macro indices | **Copy.** Add a gamma (negative-binomial) frailty per stay-week shared across days, so demand CV per week is 0.25–1.0 as in airline data [S5 §2.2] instead of Poisson's 1/√μ. Thin-data methods look far better under Poisson than reality. |
| **Repeated samples with burn-in; engine learns from its own simulated history** | One season per seed; engine sees DB the world writes | **Copy.** Run 2–3 consecutive simulated seasons per seed and score the last, so learned elasticity, pacing history and own-sold evidence are fed by the engine's own past prices. This is the only way to detect spiral-down before production. |
| Competitor RM methods | Static owner, follower, PriceLabs-style tool emulator, undercutter | Have it; add a **matching** competitor (matches our price −x%) to replicate the PODS matching experiments (Section 6.2) |
| Caching / stale availability | Scrape noise, outage flags; `stale_pms` scenario | Have it; add **channel calendar lag** (a booked night still bookable on a second channel for *h* hours) |
| Revenue scoring vs baselines | Owner net vs `current_practice`, `property_flat`; greedy hindsight upper bound (`market/scoring.py: hindsight_revenue`) | Have it; **report ROM** (9.3) |
| Strategic waiting / replanning disutility | Not modelled (shoppers do not return when prices drop) | **Copy.** A share of shoppers who reject at day *t* re-enter at *t+k* if price fell — tests whether close-in discounts teach waiting |

### 9.3 Revenue Opportunity Model (ROM)

ROM, used by Sabre/AA and many carriers, measures RM performance **after departure** by bracketing
actual revenue between two counterfactuals computed on the same (unconstrained) demand: a
**no-RM** (first-come-first-served or worst-case) revenue and a **perfect-hindsight** maximum
revenue; the score is `(actual − noRM)/(perfect − noRM)` = share of the revenue opportunity
captured [S67: https://www.rtscorp.com/airline/measuring-value-of-a-revenue-management-system/;
S68: https://researchrepository.ru.ac.za/handle/20.500.14915/9535 (South African Airways O&D ROM)].
Temath's thesis studies ROM's robustness to errors in estimated unconstrained demand and to
network/dependent demand [S66: https://digital.ub.uni-paderborn.de/hsx/content/structure/11369].
The RTS article warns that every company's objectives differ, so lift numbers from other firms are
"received with a bit of skepticism" [S67].

**Map to us:** in simulation the shoppers are known, so ROM is exact: `perfect` = the existing
`hindsight_revenue` (in owner-net terms), `noRM` = `property_flat` (or a "never change price"
policy). Report **opportunity captured %** alongside owner-net $ per policy. In production, ROM
needs unconstrained demand we do not observe; use it only in simulation and in replay where the
shopper stream is synthetic.

### 9.4 Field measurement: the Iberia "sandbox"

Talluri, Castejón, Codina & Magaz, "Proving the performance of a new revenue management system",
*JRPM* 9(4) (2010) [S69: https://econ-papers.upf.edu/papers/1196.pdf; read]: Iberia let four
control systems (incumbent man–machine process and prototypes) control the **same test flights on
alternating weeks** for nine months, with control flights on the incumbent throughout. Findings on
method: 9 months over four systems gives only ~9 weeks each, "not sufficiently large to average out
inter-week differences"; they had to **normalize by the comparable week 52 weeks earlier** and by
an **out-of-trial control flight in the same week**, delete weeks with moving holidays (Easter) and
analyse them separately, and watch for customers whose outbound and return fall in different
systems' weeks. They also argue that academic simulations "only test 'within-model' performance,
and say nothing as to the appropriateness of the model in the first place" [S69].

**Map to our field-power problem** (MDE ≈ 33% at 60 weeks/arm without variance reduction, per the
2026-10-16 build notes): the Iberia toolkit is exactly what we need — (1) **switchback by stay-week**
(engine vs current practice alternating weeks per home), (2) **ratio to the same week last year**
for that home (the CUPED-style covariate the experiment spec already plans), (3) **contemporaneous
control unit** (the other twin in the same week, or Cloud 9), (4) holidays handled as separate
strata, (5) **spill-over check**: a stay that spans a switch boundary is priced by both arms — assign
stays by check-in week. The twin control is contaminated if the twins substitute (Section 2.5), so
prefer Cloud 9 or the comp-market index as the control series for the twins.

**COAT cuts against part of this design, and that has to be faced directly.** Drissi, Ettl,
Subramanian, Sun & Xue, "Counterfactual Optimal Action Trees (COAT)" (arXiv 2607.14318, v1 15 July
2026) [S84: https://arxiv.org/abs/2607.14318; full text read 2026-10-19] report a **17-week** live
pilot (planned as 12 weeks) of **premium-seat upgrade (ancillary) pricing** with a major global
airline: **+6.9% upsell revenue per booking**, evaluated by **synthetic control** over 12 test markets
and 30 control markets (placebo p = 1/31 ≈ 0.032). It is not a fare-pricing pilot, and the paper
gives no pilot year. The authors considered and **rejected two designs this section relies on**:
"Temporal alternating between AI pricing and legacy pricing was rejected due to the
advance-purchase nature of airline bookings, which makes it impossible to cleanly align treatment
timing with observed outcomes. Year-over-year comparisons were also unsuitable, as demand patterns
during 2020–2022 were heavily distorted by the COVID-19 pandemic." Customer-level price differences
were excluded for legal, regulatory and fairness reasons.

Why check-in-week assignment can still survive here: COAT's objection is to alternating the
*selling* calendar, where a booking made in week t for a flight months later gets the treatment of
week t. We assign arms by **stay (check-in) week**, so every quote for a given stay-week, across its
whole booking window, comes from one arm, and treatment timing does align with the outcome. COAT's
YoY objection does apply in a weaker form: we have one prior season, and it was a drought season
(2025-26). So the design changes as follows: (a) keep check-in-week assignment, (b) make the
**comp-market series the primary covariate** and fit a synthetic-control estimate from comp and
market availability series as a second estimator, and (c) treat the same-week-last-year ratio as a
secondary covariate that can be dropped if its season-level fit is poor.

**Further design details the field test needs** (from Iberia [S69] §3 and our stay structure):
- **Boundary-crossing stays.** With 4–7-night LOS, many stays span two assignment weeks. Assign the
  whole stay to the arm of its **check-in** date and quote it under that arm only. Report the share
  of stays that would have straddled a boundary, and test sensitivity by excluding them (Iberia's
  analogue was outbound and return legs in different systems' weeks).
- **Observer and operator bias.** Iberia's analysts knew which system controlled which week. Here
  the operator sees both arms and can override. Log every override with its arm, pre-register the
  override rule, and report results with and without override-touched stays.
- **Unstable YoY covariate.** One prior season, a drought year, makes the ratio-to-last-year
  covariate noisy and biased. Do not let the MDE claim depend on it (see (b) above).
- **Cross-week substitution.** A guest choosing between adjacent weeks sees two arms' prices. Check
  whether bookings shift toward the cheaper arm's adjacent week; if they do, use two-week blocks.

### 9.5 Field power: what the field can and cannot detect

The shared context gives a field MDE of about **33%** at about 60 weeks per arm without variance
reduction. MDE scales with 1/√n, so the weeks needed to detect an effect of size d are
60 × (33/d)² per arm:

| True effect d | Weeks per arm at today's variance | At a 15% MDE after variance reduction (target, **assumption**) |
|---:|---:|---:|
| 33% | 60 | 12 |
| 15% | ~290 | 60 |
| 4% | ~4,080 | ~840 |
| 2% | ~16,300 | ~3,375 |
| 1% | ~65,300 | ~13,500 |

Three homes give at most about 26 winter weeks each per season. So **every R1–R4 prior in §12
(≤ ~4%) is undetectable in the field at any plausible MDE**, even after the R6 variance reduction.
The field test can catch only large failures, such as a policy that loses a third of owner net. The
evidence that R1–R4 help must come from simulation, and the simulator gate must be a
**misspecified-world** test: the simulated WTP family and arrival process differ from the engine's
own S(p) (for example a kinked PODS template or a lognormal world against a logit engine, and
over-dispersed rather than Poisson arrivals). Passing "v2 targets still pass" on a world built from
the engine's own assumptions is not evidence.

---

## 10. Transfer analysis

Our constraints: 3 homes (2 near-identical twins under one owner, Cloud 9 under another); capacity
1 per home-night; ~100 reservations of history; multi-night stays with min-stay rules; large group
parties; $1.7k–2.5k/night listed winter rates; fee-inclusive display ($600 cleaning, $75/guest, $80
insurance); owner-net objective; comp scraper anchors only ~3% of nights today.

"Value" is my judgement of expected owner-net impact for these three homes, **not a measured
number**; the measurement plan for each is in Section 12. Effort: S ≤ 1 week, M 1–3 weeks,
L > 3 weeks of engineering.

| Method | Core assumption | Holds for 3 STR homes? | Adaptation needed | Expected value (owner net) | Effort |
|---|---|---|---|---|---|
| Littlewood / EMSR-a/b protection levels | Many identical seats; independent class demand; low-before-high arrivals | **No** (capacity 1; one posted price) | Collapses to a bid-price test; use 4.4 instead | Nil as such | — |
| **Capacity-1 DP bid price** `BP_k = V_{k−1}`, price = argmax q(p)(π(p) − BP) | Arrival intensity by lead bucket and WTP distribution are estimable | **Yes, if pooled** across homes, seasons, years and market drawdown | Hazard model from `pacing_snapshots`; owner-net π; replaces M3 | **High** on peak/holiday (holds price far out) and shoulder (derives close-in discounts only where Λ is low) | M |
| Static LP bid prices (DLP) / DAVN | Large capacity and volume (asymptotic optimality) | **No** for volume; **yes** as a formulation for LOS | Use dynamic BP per night, sum over stay nights | Medium (via LOS below) | — |
| **LOS as network RM**: stay = itinerary; accept/price by Σ BP + orphan displacement | Nights are legs; displacement measurable | **Yes**; strongest on peak weeks (network RM pays at high load) | Stay-level quote; min-stay derived from BP; unify M4 + orphan scanner | **Medium–High** at Christmas/holiday weeks, low in January midweek | M–L |
| **Booking-curve / pickup forecast** vs our pace ratio | Comparable past dates exist; curve shape stable | **Partly**: shape poolable, level not per home | Additive + advanced pickup over pooled unit-nights; Bayesian shrink; net of cancellations | Medium (stabilizes price moves; feeds Λ_k) | S–M |
| **Unconstraining** (EM, PD, booking-profile) | Censoring point known; enough uncensored obs | **Different censoring** (first-booking only) | Discrete-time survival model of time-to-booking with price covariate; censor at block/min-stay; inquiries as partial demand | Medium (the remedy for own-price spiral-down) | M |
| Fare adjustment / marginal-revenue transformation | Customers buy lowest open fare; sell-up estimable | **Yes, in the continuous single-price form** | Price = BP + markup (1/b exponential; BP/2 pass-through linear); test pass-through | High (it is the same change as the BP row; not additive) | S once BP exists |
| Hybrid / Q-forecasting | Mix of fenced and price-oriented demand | Weakly (we have one product; fences = refundability, LOS, channel) | Separate refundable vs non-refundable demand if a rate plan is added | Low–Medium | M |
| Overbooking | Show-up uncertainty; finite denied-boarding cost | **No** | Do not overbook | None (negative) | — |
| **Cancellation forecasting / net pace** | Cancellation rate depends on lead, policy, channel | **Yes** | Pace on net bookings; cancellation-adjusted booking value | Low–Medium (avoids false "ahead of pace") | S |
| Refundable vs non-refundable rate plans | Customers differ in cancellation risk/WTP | **Plausibly** (VRBO/direct; Airbnb has non-refundable option) | Two price points per night (e.g. −10%); measure take-up | Low–Medium, uncertain | S (config) + measurement |
| Continuous pricing | Fixed price points constrain revenue | Already true (we post any price) | None | Nil (already have it) | — |
| Joint pricing of substitutable products (twins) | Customers choose among our products | **Yes** for twins | M5 heuristic + recapture uplift to twin BP when sibling books | Low (< 1% in airline DPE) but cheap | S |
| Competitor fare feeds / matching | Competitor price drives choice | **Yes** but capacity-1 makes comp *availability* more informative | Quality-adjusted anchor; comp drawdown into Λ_k; never "match lowest" | Medium (protects against price-war losses of 3–9% seen in PODS) | S–M |
| Shopping-data leading indicators | Search volume precedes bookings | **Partly**: we see only our direct site + inquiries | Log direct-site date searches; enter via signals ladder | Low–Medium; unknown | S |
| Outlier / event detection on booking curves | Many comparable curves | Pool at market level | Flag, don't auto-price; operator influence | Medium on event weeks | S–M |
| Analyst influences | Humans know events/groups | **Yes** (groups, events = where overrides helped) | Structured, logged demand influences; scored | Medium, if measured; negative if free-form | S |
| RL / deep learning RMS | Millions of episodes; trusted simulator | **No** | Use Bayesian learning with bounded exploration instead (M1) | Negative risk at our n | — |
| **PODS-style closed-loop, multi-season simulation** | Simulator calibrated; engine learns from own history | **Yes** | Multi-season seeds with burn-in; over-dispersed demand; matcher competitor; strategic waiters; ROM score | High for decision quality (prevents shipping spiral-prone policies) | M |
| ROM metric | Unconstrained demand known | Only in simulation | Score opportunity-captured % per policy | Medium (diagnostic) | S |
| Iberia-style switchback field test | Comparable weeks, YoY baseline | **Partly** (COAT rejects selling-date alternation and YoY baselines; stay-week assignment survives, §9.4) | Switchback by stay-week per home, comp-market covariate plus synthetic control, YoY ratio secondary, holiday strata | High for proving value (cuts MDE) | S–M |

### 10.1 Pace pricing vs a pickup forecast + bid-price threshold (required comparison)

| Aspect | Our `pace.py` today | Airline-style alternative |
|---|---|---|
| What pace measures | Portfolio on-books share in ±3 days ÷ expected share at this lead | Remaining demand forecast `Σ_{k'≤k} Λ_k'` for *this* home-night |
| Functional form | Multiplicative ratio (ranked worst in hotel/airline comparisons) | Additive/advanced pickup or hazard model |
| How it reaches price | Multiplies the comp-anchored reference by `clip(1 + 0.30(index − 1), 0.85, 1.25)` | Enters BP via `V_{k−1}`; price = argmax q(p)(π(p) − BP) |
| Time dimension | None beyond the lead-specific expected share | Explicit backward recursion: value of waiting shrinks to 0 at arrival |
| Behind pace close-in | Lowers reference ≤ 15% (plus MODEL_SPEC β guard) | Lowers price only if remaining Λ is low; Christmas behind pace at 10 days may still hold |
| Booked neighbours | Raise index (more booked → higher price) | Twin booked → recapture raises twin BP; comp booked → raises Λ |
| LOS | Separate M4 heuristic, orphan scanner | Same machinery: stay value vs Σ BP + displacement |
| Data need | `pacing_snapshots` + curve constants | Same table, modelled as survival data; plus a WTP slope prior |

The two are compatible: keep the comp anchor (it sets the WTP location), and move pace from a
price multiplier into the remaining-demand forecast that drives BP. The `DEFAULT_CURVE` constants
become the prior for the hazard model.

---

## 11. Hypotheses H2, H6, H7 in the light of airline RM; what generic STR pricers miss

**H6 (airlines/hotels far more sophisticated; STR ~10 years old).** *Supported, with a caveat.*
Airline RM has 50+ years of OR (overbooking from 1958, EMSR 1987, O&D 1990s, choice-based RM 2004,
fare adjustment 2010, continuous pricing 2019, AI pricing 2024–25). But most of that sophistication
solves **volume and network problems we do not have** (hundreds of seats, 26 classes, thousands of
O&Ds, GDS distribution constraints). The transferable core is small and old: **bid price =
value of waiting; price = bid price + WTP markup; displacement for multi-leg (multi-night) stays;
unconstrain censored demand; measure against hindsight and with switchback tests.**

**H2 — what generic STR pricers miss (airline lens).** From the public PriceLabs algorithm
descriptions summarized in dossier 04 (base price × season × day-of-week × holiday lift ×
last-minute discount inside 14 days × orphan discount × occupancy/pace rule) [S79:
https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/] — I did not
re-audit other vendors here; R4 covers that:
1. **No explicit opportunity cost.** Multiplier chains have no value-of-waiting term; last-minute
   discounts are applied by rule, not because remaining demand is low. Airline DP says the
   discount should depend on remaining arrival intensity, which is very different for Christmas
   week and mid-January.
2. **No unconstraining.** A listing that sells out a week early at a low price "looks like" strong
   pace and a correct price; airline practice would infer the price was too low.
3. **Market occupancy as pace.** Using market-wide occupancy is a reasonable leading indicator
   but is not the home's own remaining-demand forecast; luxury 16-sleepers have a different booking
   curve (they book further out) than the market's mostly small units.
4. **Nightly, not stay-level, value.** Orphan discounts treat gaps by rule; network RM treats them as
   displacement in the accept/price decision.
5. **Gross, not owner-net.** Airbnb's own tool lacks host costs [S75]; generic tools optimize
   revenue/occupancy, not owner net after a 25% management fee, channel fee and turnover cost —
   which changes the value of a short stay (one more turnover) vs a long one.
These are **plausible gaps from public descriptions, not proven deficits** — vendors may do more
than they publish (**UNVERIFIED**).

**H7 (a hyper-specialized engine can beat generic pricers).** Airline evidence suggests the edge
comes from (a) **demand forecasting specific to the market** (events, snow, I-70 access feed Λ_k)
and (b) **getting the economics right** (owner-net, LOS displacement, cancellation), not from
optimizer sophistication — the optimizer for capacity 1 is a 20-line recursion anyone could write.
Where specialization does **not** help: anything needing volume (RL, deep forecasting, per-home
elasticity) — three homes will never supply it; pooling across the Winter Park comp market is the
only data scale-up.

### 11.1 Adversarial pass: does airline RM actually deliver what it claims?

- **The 2–5% rule of thumb is rarely measured.** Industry commentator Tom Bacon writes that although
  airlines may attribute two to five percent of revenue to RM, "they don't actually measure this
  gain" and rarely know which parts of the process add value [S85: https://www.reutersevents.com/travel/node/60666;
  trade press; **dead link** (301 to the Reuters Events home page on 2026-10-19), no archive copy
  retrieved, so the quote is **UNVERIFIED**]. Almost every lift number in this dossier is a **simulation** (PODS) or a
  **self-report** (AA $1.4B, vendor 3.5–7%). The only field experiments found are Iberia's sandbox
  (which mostly documented how hard measurement is), Cohen et al.'s fare-ladder experiment, Zeni's
  analyst study, and Wyndham's two-region test.
- **RM gains depend on the baseline.** D'Haultfœuille, Wang, Février & Wilner, "Instrument-free
  demand estimation using relative prices variation, with an application to railway
  transportation" [S86: https://arxiv.org/abs/2206.04424; v6 full text read 2026-10-19], estimate
  for SNCF's iDTGV that **observed revenue (12.21 k€ per train, Table 6) is similar to or better than
  optimal uniform pricing under incomplete information (11.29–12.31 k€)** but **9–17% below** the
  optimal stopping-time strategies (13.44–14.70 k€); lower bounds keep the loss above 4.9%. The
  earlier "16.2%" in this dossier was the observed *social welfare* figure (16.23 k€), not a revenue
  gap, and is withdrawn.
- **Within-model simulation flatters.** Talluri et al. [S69] — simulations test the model against
  itself. Fiig et al.'s 10–16% hybrid-forecasting gains are against a baseline that ignores buy-down
  entirely [S24]. Our proving ground has the same risk; Section 9.2's misspecification upgrades
  (over-dispersion, strategic waiters, multi-season learning) are the mitigation.
- **Bid prices are not optimal at small scale** [S11]: the asymptotic results that justify LP bid
  prices fail at capacity 1. The exact DP of Section 4.4 sidesteps this, but its output is only as
  good as Λ_k and S(p), which at ~100 reservations are mostly prior.
- **Competition can reverse single-firm conclusions** [S61; S38's competitor caveat]: a first-mover
  gain can be erased when competitors respond. With ~280 Winter Park listings and generic pricers on
  many of them, our competitors do respond (the tool-emulator agent in the simulator).
- **Dynamic pricing can be unpopular.** Fairness perceptions depend on framing and familiarity
  [S78]; the Delta/Fetcherr episode [S49–S51] shows the political risk when pricing looks personal.

**Net:** the adversarial pass does not overturn the core recommendation (opportunity-cost pricing is
a theorem, not a vendor claim), but it lowers confidence in every *magnitude* and raises the
priority of measurement (R5, R6).

---

## 12. Ranked recommendations

Ranking = expected owner-net impact × confidence ÷ effort, for these three homes. "Expected impact"
ranges are **my priors** informed by the airline/hotel evidence above (which is mostly simulation and
mostly STALE), not forecasts; every item carries a measurement plan, and nothing should ship on
the prior. Standard measurement for engine changes: `proving_ground_exam` calibration v2, paired
held-out seeds (25+), owner-net vs `current_practice` and vs the current candidate
(`pace_learned_owner_net`), stress scenarios (no scenario loses > 5% paired owner net), plus the
new PODS-style closed-loop mode (R5). Field: switchback design (R6).

| # | Recommendation | Module(s) | Expected impact (owner net) | Confidence | Effort | Data needed | Measurement plan |
|---|---|---|---|---|---|---|---|
| **R1a** | **Finite-WTP demand model for peak-at-ceiling.** Replace the demand curve that piles recommendations on the ceiling with a finite WTP distribution that falls above market quotes. Measure it separately from the bid-price recursion | `src/bookprob`, `src/elasticity`, `src/ceiling` | Prior only; the field cannot detect a ≤4% effect. Do not assign the bid-price impact to this row | Medium–Low until a misspecified-world sim shows the ceiling share falling without hurting owner net | M | Comp quotes at peak, current ceiling distribution | Sim: share of peak recommendations at the ceiling, and Brier/reliability of P(book \| p) at high prices, on a WTP family that is not the engine's own S(p) |
| **R1b** | **Capacity-1 bid-price recursion.** Compute `V_k` per home-night by backward recursion over lead buckets; price = argmax q_k(p)·(π_owner(p) − V_{k−1}) within floor/ceiling/guardrails; retire M3's `C = q·(floor+ceiling)/2`. This is not the peak-at-ceiling fix: a bid price is ≥ 0 and only pushes price up. That repair is **R1a**, a finite WTP demand model, measured separately (§0, §3.4) | `src/compose`, `src/bookprob` (new `bidprice` helper), `src/pricing/pace.py` | +1–4% season owner net (largest on holiday/peak far-out nights, where it holds price; and on low-Λ shoulder nights, where it discounts earlier). Prior only | Medium (mechanism is textbook-optimal; magnitude depends on Λ and WTP estimates) | M | `pacing_snapshots` (have), pooled hazard estimates, WTP slope prior, owner economics (have) | Sim: paired seeds vs candidate with R1a held fixed. R1b diagnostics are owner net and close-in Christmas discount (~0), not a falling ceiling share. Ceiling share is an R1a diagnostic. ROM must be owner-net, not the gross greedy bound. Field: R6 switchback |
| **R2** | **Stay-level displacement pricing (LOS as network RM).** Quote/accept a stay by Σ BP(nights) + orphan displacement; derive min-stay from BP instead of a static table; unify M4 and the orphan scanner | `src/compose`, `src/min_stay`, `src/leakage` | +1–3% on peak/holiday weeks; ~0 midweek January (network RM pays at high load) | Medium–Low (hotel LP evidence +2.9% STALE; our gaps are few) | M–L | Same as R1b + LOS distribution by season (have, aggregate) | Sim: paired; count stranded orphan nights and their lost owner net; Christmas-week revenue per available night |
| **R3** | **Replace the multiplicative pace ratio with a pooled additive/advanced-pickup or survival (time-to-booking) forecast, net of cancellations**, and feed it into R1's Λ_k rather than multiplying price | `src/pacing`, `src/pricing/pace.py`, `src/bookprob` | +0.5–2% (fewer noisy ±11% swings; fewer false "ahead of pace" on refundable bookings) | Medium (hotel/airline comparisons favour additive; thin-data gain unproven) | S–M | `pacing_snapshots`, cancellation timestamps (aggregate), market availability drawdown from `market_snapshots` | Forecast: Brier/reliability of P(booked by stay) by lead (L1 gate), MAE not MAPE; engine: paired sim |
| **R4** | **Unconstrain own-history demand** (survival model; censor at blocks/min-stay; inquiries as demand evidence) and stop learning reference or elasticity from own sold prices alone | `src/elasticity`, `src/bookprob`, `src/pricing/pace.py: own_sold_evidence` | Same spiral-down *risk* as the rejected own-sold blend. That screen was 5 seeds and one season, not a demonstrated multi-season loss, so the earlier ~$8k-per-season figure is withdrawn; +0.5–2% is a prior | Medium | M | `pacing_snapshots`, Guesty inquiry counts (aggregate), block calendars | Closed-loop multi-season sim (R5): does the policy's season-3 owner net fall vs season-1? |
| **R5** | **PODS-style simulator upgrades:** multi-season seeds with burn-in (engine learns from its own simulated history); gamma-frailty over-dispersed weekly demand; a matcher competitor; strategic waiters; channel-lag double-book risk; ROM score | `proving_ground_exam/market/*`, `scripts/paired_market_sim.py` | Indirect but large: prevents shipping policies that look good only under Poisson/one-season assumptions | High (this is how airlines validated RM for 30 years) | M | none new | Validation gate: a misspecified-world test (simulated WTP family ≠ the engine's S(p)), not only "v2 targets still pass". Report per-policy owner-net ROM %. Rank stability between Poisson and over-dispersed worlds |
| **R6** | **Iberia-style field measurement:** switchback by check-in week per home (engine vs current practice), comp-market index as the primary covariate with a synthetic-control estimate as a second estimator (COAT rejects selling-date alternation and YoY baselines, §9.4), same-week-last-year ratio only as a secondary covariate, whole stays assigned by check-in date, overrides logged by arm, holidays as separate strata. It detects only large failures (§9.5) | `src/experiments`, `src/eval` | Not revenue itself; cuts the 33% MDE (target < 15% over two seasons — **assumption**) | Medium | S–M | Prior-year weekly aggregates per home (have/backfill), comp index | Pre-registered power calc using real weekly CV; A/A test on last season's data |
| **R7** | **Quality-adjusted comp anchor + comp availability drawdown as a demand signal; never match the lowest comp** | `src/comps`, `src/pricing/pace.py: comp_anchor`, `src/signals` | +0.5–2%; protects against PODS-measured matching losses (3–9%) in `price_war` | Medium | S–M | Scraper reliability (binding: ~67% row failure today), comp attributes (bedrooms, sleeps) | `price_war` and `supply_surge` scenarios: paired owner net vs current anchor; field: IC of comp drawdown vs our next-14-day bookings via signals ladder |
| **R8** | **Structured operator "influences"** for events and group inquiries (adjust Λ_k, logged, scored), replacing free-form price overrides | `src/review`, `src/signals`, `src/explain` | +0–2% on event weeks; negative if unstructured | Medium (hotel evidence: overrides help groups/events, hurt transient) | S | Operator input | Score each influence ex post: realized vs no-influence counterfactual price path in replay |
| **R9** | **Cancellation-aware value and a refundable vs non-refundable test** (direct + VRBO first) | `src/pricing`, Guesty rate plans (operator action), `src/eval` | Uncertain: hotel premia 10–15% suggest a ~10% non-refundable discount can raise owner net if cancellation-resale losses are material | Low | S | Per-season cancellation rate and resale outcome (aggregates) | Field: take-up rate and net realized owner net per booked night by policy; sim: cancellation hazard sweep |
| **R10** | **Own the shopping data**: log aggregate direct-site date searches and quote requests; enter as experimental signals | `src/signals/collectors`, website analytics | Unknown; airline vendor claims 8–20% forecast-error reduction (inflated) | Low | S | Website analytics (aggregate counts only, no PII) | Signals ladder IC ≥ 0.05, hit rate ≥ 0.52 on 40+ obs before any price effect |

**Do not do:** overbooking; RL/deep-learning RMS at this scale; customer-level price
personalization (legal/fairness risk shown by the Delta/Fetcherr episode and the price-
discrimination concerns in the COAT pilot); price matching the cheapest comp; sharing non-public
pricing with other PMs.

**Dependencies:** R1 → R2 (needs BP), R3/R4 feed R1's Λ_k; R5 must land before R1–R4 results are
trusted; R6 before anything leaves shadow; scraper reliability gates R7.

### 12.1 Open questions for the operator

1. Do the homes' Guesty records keep **cancellation timestamps and refund outcomes** (aggregate per
   season is enough)? R3/R9 need net-of-cancellation pace.
2. Which **rate plans** can be offered per channel (non-refundable on Airbnb/VRBO/direct), and would
   the owners accept a non-refundable discount test?
3. Are **inquiry counts by stay date** and **direct-website search logs** available as aggregates?
4. How often does a party that loses one twin **book the other** (recapture)? Even an anecdotal
   rate helps set the twin-BP uplift prior.
5. Will the owners accept a **switchback field test** (engine controls alternate check-in weeks) for
   at least one full winter, with holidays excluded or stratified?
6. Which **events and group patterns** does the operator already adjust for by hand? Those are the
   first candidates for structured influences (R8).
7. Is the 25% management fee charged on nightly rate only or also on cleaning/fees? It changes π(p)
   in R1.

---

## 13. Bibliography

Access date for all URLs: 2026-10-16. **Depth** column: *full* = primary text read in this session;
*abstract* = publisher/index abstract read; *summary* = only a search-engine or secondary summary
seen; *biblio* = bibliographic record only. Class numbers follow `00_DEPTH_STANDARD.md`
(1 academic, 2 textbook, 3 vendor/white paper/patent, 4 industry body, 5 filings/earnings,
6 government/official, 7 practitioner/trade press).

| # | Reference | URL | Class | Depth | STALE? |
|---|---|---|---|---|---|
| S1 | INFORMS, "American Airlines" (History of O.R. Excellence) | https://www.informs.org/Explore/History-of-O.R.-Excellence/Non-Academic-Institutions/American-Airlines | 4 | summary | — |
| S2 | Wikipedia, "Yield management" | https://en.wikipedia.org/wiki/Yield_management | 7 | summary | — |
| S3 | The Flying Moose, "How American Airlines weaponised data" | https://theflyingmoose.net/articles/how-american-airlines-weaponised-data | 7 | summary | — |
| S4 | Smith, Leimkuhler, Darrow (1992) "Yield management at American Airlines", *Interfaces* 22(1):8–31 | https://iaorifors.com/paper/7208 | 1 | abstract | STALE |
| S5 | McGill, van Ryzin (1999) "Revenue management: research overview and prospects", *Transportation Science* 33(2):233–256 | https://business.columbia.edu/sites/default/files-efs/pubfiles/3925/vanryzin_revenue.pdf | 1 | full | STALE |
| S6 | Wikipedia, "Littlewood's rule" | https://en.wikipedia.org/wiki/Littlewood%27s_rule | 7 | summary | — |
| S7 | arXiv 2304.07391, "Revenue management without demand forecasting: a data-driven approach for bid price generation" | https://arxiv.org/pdf/2304.07391 | 1 | summary | — |
| S8 | Brumelle, McGill (1993) "Airline seat allocation with multiple nested fare classes", *OR* 41(1):127–137 | https://ideas.repec.org/a/inm/oropre/v41y1993i1p127-137.html | 1 | abstract | STALE |
| S9 | Belobaba (1989) "Application of a probabilistic decision model to airline seat inventory control", *OR* 37(2):183–197 | https://ideas.repec.org/a/inm/oropre/v37y1989i2p183-197.html | 1 | abstract | STALE |
| S10 | Wikipedia, "Expected marginal seat revenue" | https://en.wikipedia.org/wiki/Expected_marginal_seat_revenue | 7 | full (page) | — |
| S11 | Talluri, van Ryzin (1998) "An analysis of bid-price controls for network RM", *Mgmt Sci* 44(11):1577–1593 | https://ideas.repec.org/a/inm/ormnsc/v44y1998i11-part-1p1577-1593.html | 1 | abstract | STALE |
| S12 | Williamson (1992) "Airline network seat inventory control: methodologies and revenue impacts", MIT thesis / FTL R92-3 | https://dspace.mit.edu/handle/1721.1/68123 | 1 | abstract | STALE |
| S13 | Gallego, van Ryzin (1994) "Optimal dynamic pricing of inventories with stochastic demand over finite horizons", *Mgmt Sci* 40(8):999–1020 | https://ideas.repec.org/a/inm/ormnsc/v40y1994i8p999-1020.html | 1 | abstract | STALE |
| S14 | Talluri, van Ryzin (2004) *The Theory and Practice of Revenue Management*, Kluwer/Springer, ISBN 0-387-24376-3 | https://bibsonomy.org/bibtex/6c8e140cfa7d9f3fd312df7eb5c46f59 | 2 | biblio (content from standard formulations) | STALE |
| S15 | Weatherford, Pölt (2002) "Better unconstraining of airline demand data ...", *JRPM* 1(3):234–254 | https://www.doi.org/10.1057/PALGRAVE.RPM.5170027 | 1 | abstract | STALE |
| S16 | Guo, Xiao, Li (2012) "Unconstraining methods in revenue management systems", *Adv. Oper. Res.* 270910 | https://emis.muni.cz/journals/HOA/AOR/Volume2012/270910.pdf | 1 | full | STALE |
| S17 | Weatherford, Kimes (2003) "A comparison of forecasting methods for hotel revenue management", *IJF* 19(3):401–415 | https://ecommons.cornell.edu/bitstream/handle/1813/72130/Kimes30_Comparison_of_Forecasting.pdf | 1 | full | STALE |
| S18 | Lee (1990) "Airline reservations forecasting: probabilistic and statistical models of the booking process", MIT FTL R90-5 | https://dspace.mit.edu/handle/1721.1/68100 | 1 | abstract | STALE |
| S19 | Weatherford, Belobaba (2002) "Revenue impacts of fare input and demand forecast accuracy in airline yield management", *JORS* 53(8):811–821 | https://ideas.repec.org/a/pal/jorsoc/v53y2002i8d10.1057_palgrave.jors.2601357.html | 1 | abstract | STALE |
| S20 | Swan (Boeing), spill modelling paper, WCTR Antwerp | https://wctrs-society.com/wp-content/uploads/abstracts/antwerp/V133.pdf | 1 | summary (PDF scanned, not extractable) | STALE |
| S21 | MIT OCW 1.206J (2003) lecture 5, passenger mix / recapture | https://ocw.mit.edu/courses/1-206j-airline-schedule-planning-spring-2003/7439d2a05c04bb846b5ed58b1c74360f_lec5_passenger_mix_2003.pdf | 1 | summary | STALE |
| S22 | Rennie, Cleophas, Sykulski, Dost (2021) "Identifying and responding to outlier demand in revenue management", *EJOR* | https://arxiv.org/abs/1912.05974 | 1 | abstract | — |
| S23 | Crystal, Ferguson, Higbie, Kapoor (2007) "A comparison of unconstraining methods to improve RM systems", *POM* | https://repository.gatech.edu/entities/publication/9fcfec43-a0f3-4996-ab40-1fd0a93a4e3a | 1 | summary | STALE |
| S24 | Fiig, Isler, Hopperstad, Belobaba (2010) "Optimization of mixed fare structures: theory and applications", *JRPM* 9(1/2):152–170 | https://amadeus.com/documents/en/research-papers/rpm200918a.pdf | 1 (authors partly vendor) | full | STALE |
| S25 | Belobaba (2004) "Research highlights: pricing, distribution and revenue management", MIT ICAT Industry Advisory Board | https://web.mit.edu/airlines/industry_outreach/board_meeting_presentation_files/meeting-nov-2004/Pricing&RM-Belobaba.pdf | 4 | full | STALE |
| S26 | Cooper, Homem-de-Mello, Kleywegt (2006) "Models of the spiral-down effect in revenue management", *OR* 54(5):968–987 | https://ideas.repec.org/a/inm/oropre/v54y2006i5p968-987.html | 1 | abstract | STALE |
| S27 | Talluri, van Ryzin (2004) "Revenue management under a general discrete choice model of consumer behavior", *Mgmt Sci* 50(1):15–33 | https://econ-papers.upf.edu/en/onepaper.php?id=533 | 1 | abstract | STALE |
| S28 | Cléaz-Savoyen (2005) MIT S.M. thesis on Q-forecasting and fare adjustment; related sell-up thesis | https://dspace.mit.edu/handle/1721.1/32439 ; https://dspace.mit.edu/handle/1721.1/45800 | 1 | summary | STALE |
| S29 | MIT thesis "RM methods for multiple fare structure environments" (author/year not confirmed) | https://dspace.mit.edu/handle/1721.1/44681 | 1 | summary | STALE |
| S30 | Gorin, Belobaba (2004) "Impacts of entry in airline markets ...", *JATM* 10(4):257–268 | https://ideas.repec.org/a/eee/jaitra/v10y2004i4p257-268.html | 1 | abstract | STALE |
| S31 | Weatherford (2017) "Intelligent aggressiveness ...", *Decision Sciences* 48(3):391–419 | https://www.uwyo.edu/business/about-us/directory/weatherford-larry.html | 1 | biblio | STALE |
| S32 | Rothstein (1985) "OR and the airline overbooking problem", *OR* 33(2):237 | https://pubsonline.informs.org/doi/abs/10.1287/opre.33.2.237 | 1 | abstract | STALE |
| S33 | US GAO (2019) GAO-20-191, airline denied boarding practices | https://www.gao.gov/products/GAO-20-191 | 6 | summary | STALE |
| S34 | Jia, Jin, Wagman (2021, rev. 2022) "Platform as a Rule-Maker: Evidence from Airbnb's Cancellation Policies", NBER w28878 | https://www.nber.org/papers/w28878 | 1 | abstract | STALE (2021–22) |
| S35 | "Sticky price for declining risk: the case of cancellation premia in the hotel industry" (unibz seminar) | https://www.unibz.it/it/events/137913-sticky-price-for-declining-risk-the-case-of-cancellation-premia-in-the-hotel-industry | 1 | summary | — |
| S36 | Wittman, Belobaba (2018) "Dynamic pricing mechanisms for the airline industry: a definitional framework", *JRPM* | https://dspace.mit.edu/handle/1721.1/122707 | 1 | summary | STALE |
| S37 | Wittman, Fiig, Belobaba (2018) "A dynamic pricing engine for multiple substitutable flights", *JRPM* | https://amadeus.com/documents/en/research-papers/Wittman_et_al-2018-Journal_of_Revenue_and_Pricing_Management.pdf | 1 | full | STALE |
| S38 | Szymański, Belobaba, Papen (2021) "Continuous pricing algorithms for airline RM", *JRPM* 20(6):669–688 | https://ideas.repec.org/a/pal/jorapm/v20y2021i6d10.1057_s41272-021-00350-x.html | 1 | abstract | STALE |
| S39 | Touraine (IATA) (2021) "The industry transformation to dynamic offering", *JRPM* | https://www.iata.org/contentassets/0688c780d9ad4a4fadb461b479d64e0d/journal_of_revenue_and_pricing_management_2021_touraine.pdf | 4 | full | STALE |
| S40 | IATA/ATPCO/Airline Industry Retailing, "Dynamic Offer Creation" white paper | https://www.iata.org/contentassets/0688c780d9ad4a4fadb461b479d64e0d/air-white-paper-dynamic-offer-creation.pdf | 4 | partial | STALE |
| S41 | Business Travel News Europe, Lufthansa launches NDC continuous pricing (2019) | https://www.businesstravelnewseurope.com/TMC-Distribution/Lufthansa-launches-NDC-continuous-pricing-for-lower-fares- | 7 | summary | STALE |
| S42 | Bondoux, Nguyen, Fiig, Acuna-Agost (2020) "Reinforcement learning applied to airline revenue management", *JRPM* 19(5):332–348 | https://ideas.repec.org/a/pal/jorapm/v19y2020i5d10.1057_s41272-020-00228-4.html | 1 | abstract | STALE |
| S43 | Shihab, Logemann, Thomas, Wei (2019) "Autonomous airline revenue management: a deep RL approach", arXiv 1902.06824 | https://arxiv.org/abs/1902.06824 | 1 | abstract | STALE |
| S44 | FLYR resource hub (Revenue OS claims) | https://flyr.com/resource-hub/delivering-network-wide-revenue-insights/ | 3 | summary | — |
| S45 | GlobeNewswire (2024) "Virgin Atlantic turns to FLYR for ancillary revenue management" | https://www.globenewswire.com/fr/news-release/2024/09/23/2951096/0/en/Virgin-Atlantic-Turns-to-FLYR-for-Ancillary-Revenue-Management.html | 3 | summary | — |
| S46 | PROS case study, WTP forecasting at a global airline | https://pros.com/learn/home/global-airline-increases-passenger-revenue-willingness-to-pay-forecasting | 3 | summary | — |
| S47 | PROS Real-Time Dynamic Pricing listing, Aviation Festival Asia 2025 | https://app.swapcard.com/event/aviation-festival-asia-2025/product/UHJvZHVjdF8xMjM4NDIy | 3 | summary | — |
| S48 | Aviation Week, "Generative AI 'super analyst' may change how airlines set prices" (Fetcherr) | https://aviationweek.com/air-transport/airlines-lessors/generative-ai-super-analyst-may-change-how-airlines-set-prices | 7 | summary | — |
| S49 | Sen. Blumenthal press release on letter to Delta (July 2025) | https://www.blumenthal.senate.gov/newsroom/press/release/video-blumenthal-and-colleagues-demand-answers-from-delta-ceo-as-company-moves-toward-ai-price-model-to-set-airfares | 6 | summary | — |
| S50 | Atlanta News First (2025) on Delta AI pricing expansion | https://www.atlantanewsfirst.com/2025/07/22/delta-expand-its-ai-ticket-pricing-model-disdain-some-lawmakers-consumer-advocates | 7 (reports earnings call, class 5 primary not retrieved) | full (article) | — |
| S50b | AJC (2025) "Delta counters AI pricing backlash ..." | https://ajc-ajc-prod.cdn.arcpublishing.com/business/2025/08/delta-counters-ai-pricing-backlash-insists-it-hasnt-ever-used-personal-data | 5/7 (company letter as reported) | summary | — |
| S51 | Rep. Garcia et al., letter to Delta (Nov 5 2025) | https://chuygarcia.house.gov/sites/evo-subsites/chuygarcia.house.gov/files/evo-media-document/letter-to-delta-re-ai-pricing-11.5.25.pdf | 6 | summary | — |
| S52 | Travolution, "Infare launches Pharos ..." | https://www.travolution.com/news/travel-sectors/air/infare-launches-pharos-to-provide-next-generation-revenue-management-for-airlines/ | 3/7 | summary | — |
| S53 | Lua, W. F. (2007) "Matching of lowest fare seat availability in airline revenue management systems", S.M. thesis, MIT (advisor Belobaba). Abstract: matching airline loses up to 9.2% (symmetric market); legacy loses 3.4–8.5% (four-airline network) | https://dspace.mit.edu/handle/1721.1/42054 (corrected from handle 60708, which is a different thesis) | 1 | abstract | STALE |
| S54 | US DOJ press release (1994), ATPCO settlement | https://justice.gov/archive/atr/public/press_releases/1994/211786.htm | 6 | summary | STALE |
| S55 | Federal Register 59(62), 31 Mar 1994, US v. ATPCO proposed final judgment | https://www.govinfo.gov/content/pkg/FR-1994-03-31/html/94-7672.htm | 6 | summary | STALE |
| S56 | Cohen, Jacquillat, Serpa, Benborhoum (2023) "Managing airfares under competition: insights from a field experiment", *Mgmt Sci* 69(10):6076–6108 | https://ideas.repec.org/a/inm/ormnsc/v69y2023i10p6076-6108.html | 1 | abstract | — |
| S57 | Calvano, Calzolari, Denicolò, Pastorello (2020) "Artificial intelligence, algorithmic pricing, and collusion", *AER* 110(10):3267–3297 | https://art.torvergata.it/bitstream/2108/303883/1/aer.20190623.pdf | 1 | abstract | STALE |
| S58 | Baker McKenzie (2025) "United States: Ninth Circuit on algorithmic pricing" (Gibson v. Cendyn) | https://www.bakermckenzie.com/en/insight/publications/alerts/2025/08/united-states-ninth-circuit-on-algorithmic-pricing | 7 (reports a court ruling, class 6) | summary | — |
| S59 | PROS/Emirates, "Quantifying the performance gain of using shopping data in fare pricing" | https://pros.com/?p=51189 | 3 | summary (404 on fetch) | — |
| S60 | Williams (2022) "The welfare effects of dynamic pricing: evidence from airline markets", *Econometrica* 90(2):831–858 | https://www.econometricsociety.org/publications/econometrica/2022/03/01/welfare-effects-dynamic-pricing-evidence-airline-markets | 1 | abstract | STALE (just) |
| S61 | Hortaçsu, Öry, Williams (2022) "Dynamic price competition" (working paper) | (seen in search results alongside S60; not fetched) | 1 | summary | STALE |
| S62 | Garrow (2022) RM workshop deck, Northwestern Transportation Center | https://transportation.northwestern.edu/docs/2022/20220504_garrow-rm-workshop.pdf | 1/7 | summary | STALE |
| S63 | Koupriouchina (2019) *Judgmental adjustments in revenue management*, Leiden PhD | https://openaccess.leidenuniv.nl/handle/1887/80328 | 1 | summary | STALE |
| S64 | Koupriouchina, van der Rest, Schwartz (2023) *Tourism Economics* 29(8):2143–2164 | https://ideas.repec.org/a/sae/toueco/v29y2023i8p2143-2164.html | 1 | abstract | — |
| S65 | Zeni (2003) "The value of analyst interaction with revenue management systems", *JRPM* 2(1) | https://iaorifors.com/paper/63379 | 1 | abstract | STALE |
| S66 | Temath (2011) *Performance measurement in airline RM* (ROM robustness) | https://digital.ub.uni-paderborn.de/hsx/content/structure/11369 | 1 | summary | STALE |
| S67 | RTS, "Measuring value of a revenue management system" | https://www.rtscorp.com/airline/measuring-value-of-a-revenue-management-system/ | 3/7 | summary | — |
| S68 | Rhodes University mini-thesis, SAA O&D RM performance measurement (ROM) | https://researchrepository.ru.ac.za/handle/20.500.14915/9535 | 1 | summary | — |
| S69 | Talluri, Castejón, Codina, Magaz (2010) "Proving the performance of a new revenue management system", *JRPM* | https://econ-papers.upf.edu/papers/1196.pdf | 1 | full | STALE |
| S70 | Belobaba (2006) "Introduction to PODS passenger choice model", MIT 16.75J lecture | https://ocw.iti.hr/courses/aeronautics-and-astronautics/16-75j-airline-management-spring-2006/lecture-notes/lect6a.pdf | 1 | full | STALE |
| S71 | Zhang, Weatherford (2017) "Dynamic pricing for network RM: a new approach and application in the hotel industry", *INFORMS J. Computing* | https://danzhang.com/papers/HotelPricing_Final.pdf | 1 | full (intro/lit) | STALE |
| S72 | Wang, McGuire, Terbush, Towns, Anderson (2021) "Choice-based dynamic pricing for vacation rentals", *Interfaces* 51(6):450–462 | https://ideas.repec.org/a/inm/orinte/v51y2021i6p450-462.html | 1 | abstract | STALE |
| S73 | Ye et al. (2018) "Customized regression model for Airbnb dynamic pricing", KDD (summary by A. Colyer) | https://blog.acolyer.org/2018//03/customized-regression-model-for-airbnb-dynamic-pricing/ | 1/7 | summary | STALE |
| S74 | Zhang, Mehta, Singh, Srinivasan (2021) "Can an AI algorithm mitigate racial economic inequality? ... Airbnb", *Marketing Science* 40(5) | https://pubsonline.informs.org/doi/fpi/10.1287/mksc.2021.1295 | 1 | summary | STALE |
| S75 | Foroughifar, Mehta, "The challenges of deploying an algorithmic pricing tool: evidence from Airbnb", *Marketing Science* | https://pubsonline.informs.org/doi/abs/10.1287/mksc.2024.0964 | 1 | abstract | — |
| S76 | Ferreira, Simchi-Levi, Wang (2018) "Online network revenue management using Thompson sampling", *OR* 66(6):1586–1602 | https://dspace.mit.edu/handle/1721.1/125757 | 1 | abstract | STALE |
| S77 | den Boer (2015) "Dynamic pricing and learning: historical origins, current research, and new directions", *Surveys in OR & MS* 20(1):1–18 | https://research.utwente.nl/en/publications/dynamic-pricing-and-learning-historical-origins-current-research--2/ | 1 | biblio | STALE |
| S78 | Kimes, Wirtz (2003) perceived fairness of RM (golf), *JRPM*; Wirtz, Kimes (2007) | https://ecommons.cornell.edu/entities/publication/db914141-6f90-4631-b2c8-b5696ac85190 | 1 | abstract | STALE |
| S79 | PriceLabs, "Overview of PriceLabs dynamic pricing algorithm, part 1" (via dossier 04) | https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/ | 3 | via dossier 04 (not re-read) | — |
| S80 | Phillips, R. (2005; 2nd ed. 2021) *Pricing and Revenue Optimization*, Stanford University Press | (book; not read this session) | 2 | biblio | — |
| S81 | Belobaba, P., Odoni, A., Barnhart, C. (eds.) (2009; 2nd ed. 2015) *The Global Airline Industry*, Wiley | (book; not read this session) | 2 | biblio | STALE |
| S82 | Ainora, "Vacation rental cancellation statistics (2026)" | https://ainora.lt/blog/vacation-rental-cancellation-statistics-2026 | 7 (weak) | summary | — |
| S83 | PROS, "COVID task force 2: revenue management under lockdown" | https://quasi.pros.com/covid-task-force-2-revenue-management-under-lockdown/ | 3 | summary | STALE |
| S84 | Drissi, Ettl, Subramanian, Sun & Xue (2026) "Counterfactual Optimal Action Trees (COAT)", arXiv 2607.14318: 17-week premium-seat upsell pilot, +6.9%, synthetic control; rejects temporal alternation and YoY baselines | https://arxiv.org/abs/2607.14318 | 1 | full (read 2026-10-19) | — |
| S85 | Bacon, "Lost and found: how airline RM can make a comeback", Reuters Events Travel | https://www.reutersevents.com/travel/node/60666 (**dead**: 301 to home page, 2026-10-19; quote UNVERIFIED) | 7 | summary | — |
| S86 | D'Haultfœuille, Wang, Février & Wilner, "Instrument-free demand estimation using relative prices variation, with an application to railway transportation", arXiv 2206.04424 (v6). Table 6: observed revenue 12.21 k€ vs 13.44–14.70 k€ under stopping-time strategies | https://arxiv.org/abs/2206.04424 | 1 | full (tables read 2026-10-19) | STALE (data) |
| S87 | Li, Granados, Netessine (2014) "Are consumers strategic? Structural estimation from the air-travel industry", *Mgmt Sci* 60; U-Michigan press release | https://pubsonline.informs.org/doi/references/10.1287/mnsc.2013.1860 ; https://news.umich.edu/?p=22497 | 1 | abstract + press release | STALE |
| S88 | Gallego, G. & Topaloglu, H. (2019) *Revenue Management and Pricing Analytics*, Springer | https://www.springer.com/in/book/9781493996049 | 2 | chapter list only | — |
| S89 | Boyd, E. A. & Kallesen, R. (2004) "The science of revenue management when passengers purchase the lowest available fare", *JRPM* 3(2):171–177 | https://www.iaorifors.com/paper/63773 | 1 | abstract | STALE |
| S90 | Cooper, W. L., Homem-de-Mello, T. & Kleywegt, A. J. (2015) "Learning and pricing with models that do not explicitly incorporate competition", *Operations Research* 63(1):86–103 | https://ideas.repec.org/a/inm/oropre/v63y2015i1p86-103.html | 1 | abstract | STALE |
| S91 | Vulcano, G., van Ryzin, G. & Ratliff, R. (2012) "Estimating primary demand for substitutable products from sales transaction data", *Operations Research* 60(2):313–334 | https://ideas.repec.org/a/inm/oropre/v60y2012i2p313-334.html | 1 | abstract | STALE |
| S92 | Constellation Research and StockStory reports of Delta's Q2-2025 earnings call (Fetcherr AI pricing share) | https://www.constellationr.com/insights/news/delta-starting-scale-its-ai-driven-dynamic-pricing-system ; https://stockstory.org/us/stocks/nyse/dal/news/earnings-call/5-must-read-analyst-questions-from-deltas-q2-earnings-call | 7 | summary | — |
| S93 | Sabre Air Price IQ / AirVision Dynamic Availability (vendor page; TTG Asia 2018 launch report) | https://sabre.com/?p=39090 ; https://www.ttgasia.com/2018/09/11/sabre-launches-new-dynamic-pricing-solutions-for-airlines/ | 3/7 | summary | STALE (2018) |
| S94 | Business Travel News, "Giving the big guns more firepower" (MIDT vendor claims: Amadeus 1–3%, Sabre +7% share); supplied by the R1 review, not re-opened by the author | https://www.businesstravelnews.com/More-News/Giving-The-Big-Guns-More-Firepower | 7 | via reviewer | STALE |
| S95 | Lufthansa Group × PROS press releases (2022 RM + RTDP consolidation; 2025 Dynamic Ancillary Pricing; 2026 renewal) | https://www.businesswire.com/news/home/20220712005223/en ; https://www.businesswire.com/news/home/20250128177013/en ; https://pros.com/news/lufthansa-group-extend-strategic-partnership/ | 3 | summary | — |

S80 and S81 are the canonical textbooks for pricing optimization and airline RM context; they are
listed as the standard references the formulations above follow, but **no claim in this dossier
rests on them alone**.


---

## Appendix A. Search log

Tool: WebSearch (standard mode unless marked *ext* = extended), WebFetch, and direct PDF download
+ text extraction for open-access PDFs. Passes: **B** = broad, **S** = specific (named methods,
people, papers), **A** = adversarial. 73 queries issued; 4 failed on a session rate limit and were
re-run in substance later (marked ✗).

| # | Pass | Query (abbrev.) | Yield |
|---|---|---|---|
| 1 | S | Smith Leimkuhler Darrow 1992 DINAMO $1.4B | S4 abstract; INFORMS history S1 |
| 2 | S | Littlewood 1972 two-fare rule | S6, S7 |
| 3 | S | Belobaba EMSR 1987/1989 *OR* | S9; EMSR-b refinement note |
| 4 | S | Brumelle McGill 1993 nested fare classes | S8 |
| 5 | B | People Express Ultimate Super Saver / Burr quote | S2, S3; quote unverified |
| 6 | S | Weatherford & Pölt 2002 unconstraining EM/PD | S15 (2–12%) |
| 7 | S | Guo, Xiao, Li 2012 unconstraining review | S16 (downloaded, read) |
| 8 | S | Weatherford & Kimes 2003 hotel forecasting | S17 (downloaded, read) |
| 9 | S | Fiig, Isler, Hopperstad, Belobaba 2010 fare adjustment | S24 (downloaded, read) |
| 10 | S | Belobaba/Hopperstad Q-forecasting, hybrid, sell-up PODS | S28 (sell-up 3%) |
| 11 | S | Cooper, Homem-de-Mello, Kleywegt spiral-down | S26 |
| 12 | S | Talluri & van Ryzin 2004 choice-based RM | S27 |
| 13 | S | Williamson 1992 thesis / DAVN | S12 (2–4% at >85% LF) |
| 14 | S | Talluri & van Ryzin 1998 bid prices | S11 |
| 15 | S | Gallego & van Ryzin 1994 dynamic pricing | S13 |
| 16 | S | Weatherford & Belobaba 2002 forecast accuracy | S19 |
| 17 | S | Lee 1990 "10% forecast accuracy" | S18 (0.5–3%) |
| 18 | S | Wittman & Belobaba dynamic pricing mechanisms | S36, S37 (downloaded, read) |
| 19 | B | ATPCO dynamic pricing / Lufthansa continuous pricing | S41 |
| 20 | B | IATA dynamic offer creation NDC | S39, S40 (downloaded, read) |
| 21 | S | Bondoux et al. 2020 RL airline RM | S42, S43 |
| 22 | S *ext* | Fetcherr LMM uplift claims WestJet/Virgin/Azul | S48; no audited % |
| 23 | B | FLYR revenue OS uplift | S44, S45 (vendor) |
| 24 | A | Delta/Fetcherr AI pricing senators | S49, S50b, S51 |
| 25 | S | Talluri & van Ryzin textbook LOS/displacement | S14 biblio |
| 26 | S | Rothstein 1985 overbooking; denied boarding | S32, S33 |
| 27 | B | Airbnb cancellation policy economics | S34, S35 |
| 28 | S | "advanced pickup" definition | S17 cross-check |
| 29 | S | spill & recapture, Swan formula | S20, S21 |
| 30 | S | Rennie et al. outlier demand | S22 |
| 31 | S | Boyd & Kallesen hybrid forecasting (1) | not found → UNVERIFIED |
| 32 | S | Belobaba/Hopperstad 2004 AGIFORS unrestricted fares | S25 (downloaded, read) |
| 33 | S | Gorin & Belobaba 2004 LCC entry | S30 |
| 34 | S | Q-forecasting/fare adjustment MIT theses | S28, S29 |
| 35–38 | — | analyst overrides; ROM; Mukhopadhyay; PODS choice | ✗ rate-limited |
| 39 | S | RM analyst overrides "user influences" | S22, S63 lead, Zeni lead |
| 40 | S | Zeni 2003 analyst value (1) | not found |
| 41 | S | Revenue Opportunity Model perfect hindsight | S66, S67, S68 |
| 42 | S | PODS passenger choice model decision window | S70 (downloaded, read) |
| 43 | B | Infare competitor fare intelligence | S52 (vendor) |
| 44 | S | fare matching / price war PODS | S53 |
| 45 | A | US v. ATPCO 1994 consent decree | S54, S55 |
| 46 | B | shopping/search data as leading indicator | S59, S60 lead, S62 |
| 47 | S | Williams 2022 *Econometrica* | S60, S61 |
| 48 | S | Lufthansa/BCG/Amadeus continuous pricing gains | S38 |
| 49 | S | PROS WTP / RTDP uplift | S46, S47 (vendor) |
| 50 | S | Ye et al. 2018 Airbnb dynamic pricing | S73; Wyndham lead |
| 51 | S | Airbnb smart pricing adoption effects | S74, S75 lead |
| 52 | S | hotel LOS network RM, Bitran–Mondschein | S71 (downloaded, read) |
| 53 | S | Choice-based dynamic pricing for vacation rentals | S72 |
| 54 | A | challenges of deploying algorithmic pricing (Airbnb) | S75 |
| 55 | S | Boyd & Kallesen priceable/yieldable (2) | not found → UNVERIFIED |
| 56 | S | den Boer 2015 pricing & learning survey | S77 |
| 57 | S | airline RM A/B / field experiments | S69 (downloaded, read), S84, S56 lead |
| 58 | A | COVID broke airline RM forecasting | S83 |
| 59 | B | STR cancellation rates | S82 (weak) |
| 60 | B | hotel overbooking/cancellation, refundable rates | background only |
| 61 | A | Fetcherr criticism / black-box | no expert critique found |
| 62 | S | Cohen et al. airfare field experiment | S56 |
| 63 | S | Mukhopadhyay et al. 2007 | not found → UNVERIFIED |
| 64 | S | Kimes & Wirtz fairness | S78 |
| 65 | S | Weatherford 2017 *Decision Sciences* | S31 biblio |
| 66 | S | Thompson sampling network RM | S76 |
| 67 | A | Gibson v. Cendyn 9th Cir. 2025 | S58 |
| 68 | A | Calvano et al. algorithmic collusion | S57 |
| 69 | S | Koupriouchina override accuracy | S63, S64 |
| 70 | S | Delta Q2 2025 earnings call transcript | not found → UNVERIFIED |
| 71 | A | RM benefits overstated / independent evaluation | S85, S86, Zeni S65 found |
| 72 | S | NBER w28878 authors | S34 confirmed |
| 73 | A | strategic customers airline evidence | S87 |

Direct fetches/downloads (not counted above): McGill & van Ryzin PDF (read), Guo et al. PDF (read),
Weatherford & Kimes PDF (read), Fiig et al. PDF (read), Belobaba 2004 deck (read), Wittman et al.
PDF (read), Touraine PDF (read), IATA DOC white paper (partial), MIT PODS lecture (read), Iberia
paper (read), Zhang & Weatherford PDF (read intro and literature), Wikipedia EMSR, IDEAS/IAOR
abstract pages (S4, S9, S38), arXiv abstracts (S22, S43), Atlanta News First article; failed:
Swan WCTR PDF (scanned), PROS shopping-data page (404), MIT DSpace pages (empty render).

---

## Appendix B. Self-audit against `00_DEPTH_STANDARD.md`

| MUST | Status | Evidence |
|---|---|---|
| Cite every non-obvious factual claim inline with URL (or full reference) and access date | **PASS** | Inline [Sn: URL] throughout; global access date 2026-10-16 stated at top and in §13 |
| ≥ 40 distinct sources | **PASS** | 96 bibliography entries (S1–S95 + S50b). S88–S95 were cited in the body after the fix pass but had no §13 rows until the 2026-10-19 audit |
| ≥ 4 source classes | **PASS** | Class 1 academic: 56; class 2 textbook: 3 (biblio only); class 3 vendor: 9; class 4 industry body: 4 (INFORMS, IATA ×2, MIT ICAT/PODS consortium); class 5 filings/earnings: 1 (weak, as reported); class 6 government: 5 (GAO, DOJ, Federal Register, Senate, House); class 7 trade press/practitioner: 10 → 7 classes, 6 with ≥ 3 sources |
| Read primary sources where they exist; say so if paywalled | **PARTIAL** | The review counted 41 of 88 sources at search-summary depth, including open-access MIT theses and arXiv papers. The 2026-10-19 audit read S84 and S86 in full and S53's abstract; S7, S12, S28, S29 and S33 are still summary-only. 13 primary texts read in full (S5, S10, S16, S17, S24, S25, S37, S39, S69, S70, S71, S84, S86); many classics (Belobaba 1989, Talluri–van Ryzin 1998/2004, Gallego–van Ryzin, Cooper et al.) are paywalled and cited from abstracts, marked "abstract" in §13; Talluri & van Ryzin and Phillips textbooks not available in session (marked biblio) |
| Mark unverified as UNVERIFIED; flag > 3-year-old data as STALE; no fabricated citations | **PASS, with corrections** | UNVERIFIED used for the Burr quote, Mukhopadhyay 2007, the Delta transcript, S29, S35, S59, and the S85 quote (dead link). Boyd & Kallesen is now cited to *JRPM* 3(2):171–177 (2004). No citation was fabricated, but three were wrong as first written: S53 pointed to the wrong thesis (handle 60708, corrected to 42054), S86's "16.2%" was a welfare figure, and S84's pilot was ancillary seat pricing, not fares |
| Search in several passes: broad, specific, adversarial | **PASS** | Appendix A: B = 9, S = 51, A = 9 successful queries (+4 rate-limited, re-run); §11.1 adversarial synthesis |
| Explain mechanisms with implementable math (objective, inputs, estimation, decision rule) | **PASS** | Littlewood, EMSR-a/b, DAVN/bid-price LP, DP and Gallego–van Ryzin (§1); pickup forms and EM steps (§2); marginal-revenue transformation and 1/b fare modifier (§3.3); linear-demand BP pass-through derivation (§3.4); capacity-1 recursion and LOS rule (§4.4); DPE objective (§5.2); PODS WTP form (§9.1); ROM formula (§9.3) |
| Quantified evidence of impact, with who measured and conflicts | **PASS** | AA $1.4B (self-report), unconstraining 2–12%, forecast 0.5–3%, network 2–4%, HF/FA 10–16% (+ authors' vendor ties), DPE 5–7% / <1%, CP 1.2–2.0%, vendor 3.5–7% marked VENDOR, Wyndham +3.5/+5.2% (conflict noted), Airbnb smart pricing +8.6% (observational), matching losses 3.4–9.2%, override evidence (n = 20M forecasts) |
| Map every finding to this engine (module + owner-net measurement) | **PASS** | Each section ends with a transfer paragraph naming modules; §10 table; §12 table with module and measurement plan per item |
| Honest transferability (small inventory, thin data, LOS, groups, high prices, fees) | **PASS** | §10 table "holds?" column; explicit "does not transfer" for EMSR, LP bid prices, overbooking, RL, continuous pricing |
| "What generic STR pricers miss" note (H2) | **PASS** | §11, with caveat that it rests on public PriceLabs descriptions and defers to R4 |
| Ranked recommendations with impact, confidence, effort, data, measurement | **PASS** | §12 R1–R10 table + "do not do" list + dependencies |
| Open questions for the operator | **PASS** | §12.1 (7 questions) |
| Self-audit table | **PASS** | This table |
| Keep a running search log | **PASS** | Appendix A (73 queries + fetch list) |
| Prefer 2020–2026 sources and include classics | **PARTIAL PASS** | 2020–2026: S22, S34, S38, S39, S42, S44–S51, S56–S58, S60, S64, S72, S74, S75, S84, S85, S86 and others; but the core airline method evidence is genuinely 1972–2010 (STALE) because the field's foundational results are that old — flagged, not hidden |
| If finished early, run another adversarial pass | **PASS** | Second adversarial pass (queries 71–73) added §11.1, S85–S87, and corrected the Zeni and NBER citations |
| Public-repo boundaries (no booked revenue, Guesty ids, names, guest data) | **PASS** | Only public listed-rate ranges from the shared context and simulated owner-net figures already in repo docs; no guest data queried |

**Known gaps a reviewer should press on:** (1) the classic paywalled papers were read at abstract
level only; (2) no airline primary filing (10-K / earnings transcript) was retrieved — the Delta
remarks rest on press reports; (3) the Swan spill formula is unverified, and the §1.7 DP statements
have not been checked against Gallego & Topaloglu (2019) [S88]; (4) all magnitudes in §12 are priors, not estimates.

## Appendix C. Response to review

Fix pass by the author (2026-10-17), consistency pass (2026-10-17), and close-out audit
(2026-10-19). The 2026-10-19 audit checked each fix against the body text, not against the earlier
narrative summary, and reopened S53, S84, S85 and S86.

| # | Status | What changed or why not |
|---|---|---|
| 1 | applied | §0 item 1 and §3.4 state the Poisson / sparse-arrival condition; §3.4 table gives pass-through 0.99 → 0.17 as Λ rises. |
| 2 | applied | §3.4 "Units": rate-unit bid price (V − m)/s with s = 0.595 from `owner_terms()`; $0.84 linear, about $1.68 exponential. |
| 3 | applied | §0 item 2, §3.4 and §12 split R1a (demand model) from R1b (recursion), each with its own diagnostics. The §12 table was aligned in the 2026-10-17 consistency pass. |
| 4 | applied | §3.4 item 4: the PODS template is flat below base; use a smooth S(p) and keep the kinked form as a simulator world. |
| 5 | applied (2026-10-19) | §9.4 rewritten from the COAT full text: ancillary premium-seat pricing, 17 weeks, +6.9%, synthetic control, explicit rejection of temporal alternation and YoY baselines. Argues why check-in-week assignment survives and moves the primary covariate to the comp-market series with a synthetic-control second estimator. The earlier "2023 pilot" date is removed; the paper gives no pilot year. |
| 6 | applied (2026-10-19) | §9.4 adds boundary-crossing stays, operator and observer bias, YoY covariate instability, and cross-week substitution. Before this audit these appeared only in this appendix. |
| 7 | applied (2026-10-19) | New §9.5 with the power table (60 × (33/d)² weeks per arm). §0 item 5 already pointed to §9.5, which did not exist until this audit. The R5 gate is a misspecified-world test (§9.5, §12 R5). |
| 8 | applied | §0 item 4 and §12 R4: "same risk", 5-seed one-season screen, the ~$8k figure withdrawn. |
| 9 | applied (2026-10-19 for §13) | §6.2 already used handle 42054. The §13 row still pointed to 60708 with "author not confirmed"; it now names Lua (2007) and quotes the abstract figures. Read at abstract depth, not full text. |
| 10 | applied (2026-10-19) | §11.1 now names the authors and uses Table 6: observed revenue 12.21 k€ against 13.44–14.70 k€, a 9–17% gap. "16.2%" was the welfare figure and is withdrawn. |
| 11 | partly | §5.4 says S50 reports 3% of *flights* and attributes the 20% target differently. No source carrying Hauenstein's Q2-2025 remarks or the transcript was retrieved, so the wording stays UNVERIFIED. |
| 12 | applied | §5.4 VENDOR table has Fetcherr "6–9%" (S48). |
| 13 | applied (2026-10-19) | S85 marked dead: a 301 to the Reuters Events home page. No archive copy was retrievable from this environment, so the quote is UNVERIFIED. |
| 14 | applied | §2 cites *JRPM* 3(2):171–177 (2004). The self-audit and known-gaps list still called it unverified until 2026-10-19; both are corrected. |
| 15 | applied | Vulcano, van Ryzin & Ratliff (2012) in §2.2. |
| 16 | applied | Cooper, Homem-de-Mello & Kleywegt (2015) in §3.2 and the bibliography. |
| 17 | applied | §5.4 adds Sabre Air Price IQ / Dynamic Availability, Amadeus, Lufthansa–PROS RTDP and Dynamic Ancillary Pricing, and "no BCG role found". |
| 18 | applied (§7 on 2026-10-19) | §5.4 (Amadeus row) and §6.1 had MIDT and OAG, but §6.1 pointed to a §7 that did not mention MIDT. §7 now has a MIDT bullet mapped to comp availability drawdown. |
| 19 | applied | §3.5 adds the S87 counterfactual (strategic consumers need not reduce revenue; non-decreasing commitments can hurt leisure markets) and tempers the close-in stance. |
| 20 | partly | S84 and S86 were read in full on 2026-10-19, and S53 at abstract depth. S7, S12, S28, S29 and S33 are still at summary depth. Gallego & Topaloglu (2019) is already cited in §1.7 as S88 (chapter list only), but the §1.7 DP statements were **not** re-checked against it. |
| 21 | applied | §9.3 notes that `scoring.hindsight_revenue` is a gross greedy bound and that an owner-net hindsight is needed before any ROM % is reported. |
| 22 | partly | §12 labels every impact as a prior and says the field cannot detect it (§9.5). Per-row transfer reasoning is still brief, and R1b's effort is still "M" even though it depends on R5. Treat all §12 magnitudes as unranked priors. |
| 23 | applied (2026-10-19) | Appendix B now rates primary-source reading PARTIAL (41/88 summary-only at review), and the citation row records the three citations that were wrong as first written: S53, S86 and S84. |
