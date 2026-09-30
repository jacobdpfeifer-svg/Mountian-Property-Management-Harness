# Model spec (M1–M5)

Date: 2026-09-29
Chosen from dossier 5. All flags default **off** in `config/policies/default.yaml` under `models:`. Flag-off output matches the post-correction baseline defined in the Phase 3 report.

Sensible combinations for the ladder: each flag alone; M1+M2; M2+M4; M1+M2+M5. Not a full factorial.

## M1 — learned price sensitivity

Prior, by season, from `booking_probability.elasticity_by_season` (peak −0.65, and the other published constants).

On resolved nights with `stay_date < as_of` and a known as-of price (the listed price on the latest pacing row before the booking, or the booked price if no snapshot):

Let `r_hi` and `r_lo` be book rates above and below the median price, with counts `n_hi` and `n_lo`. If both counts are at least 8 and the median prices differ:

`β_hat = ((r_hi / r_lo) - 1) / ((P_hi / P_lo) - 1)`

clipped to [−2.5, −0.3]. If the ratio is undefined, `β_hat = β_prior`.

`β_post = (40 * β_prior + n * β_hat) / (40 + n)` with `n = n_hi + n_lo`.

Thompson (only if the night’s demand strength is below the peak-blackout threshold, so blackout nights are not explored): draw

`β = clip(Normal(β_post, 0.35 / sqrt(40+n)), -2.5, -0.3)`

using a generator seeded by `(property_id, stay_date, as_of)`, so replay is reproducible. The price that follows is still passed through move caps, floor, and ceiling.

Interim guard, same flag: if the season is `peak_ski`, `pacing_ratio` is not null and `< 0.70`, and lead time ≤ 21, set `β = min(β, -1.05)` after the draw (or after the posterior if sampling is off because of blackout). A peak night behind pace inside three weeks cannot keep an inelastic slope.

Reason code `learned_elasticity`. Contribution in dollars: optimum with `β_post` minus optimum with `β_prior`, measured before guardrails.

Failure: no price variation → `β_post = β_prior` → no change, which is correct. Do not shrink κ to force a move.

## M2 — demand level moves price

`price_ref' = price_ref * clip(1 + 0.15*(pace-1) + 0.10*(sqi-1) + 0.10*event, 0.85, 1.20)`

`pace` is `pacing_ratio` or 1 if null. `sqi` is the snow index if the feature has one, else 1. `event` is 1 on a configured holiday, else 0.

The booking curve’s `price_ref` becomes `price_ref'`. `p_ref` (the probability level) is unchanged. Because `P* = price_ref * (β-1)/(2β)`, the optimum moves in proportion to `price_ref'`.

Reason code `demand_level`. Dollars: optimum after the shift minus optimum before, pre-guardrail.

Consumer-layer indicators (Phase 4) add a further term `0.05 * macro_z` only when this flag is on and a shadow observation exists at `as_of`. They do nothing while the flag is off.

Failure: stacking on top of ceiling lifts. The dollar reason makes the double count visible. Weights are not tuned to a score.

## M3 — one-step booking horizon

Let `q` be the lead-bucket book rate from `_lead_observations`, shrunk with k=12 toward the season prior. Continuation value

`C = q * (floor + ceiling) / 2`

Pick the grid price maximizing `prob(P) * P + (1 - prob(P)) * C` instead of `prob(P) * P`.

Reason code `booking_horizon`. Dollars: this price minus the myopic RevPAN price, pre-guardrail.

Failure: a high `q` makes `C` large and the model refuses to discount. Shrinkage and the clamp to the floor limit that. This is not a full dynamic program.

## M4 — stay pricing

Candidate lengths: the distinct `min_nights` values already in `min_stay_rules` for that season, plus the gap length if an orphan gap is shorter than the standing rule.

For each candidate `m`, value = sum of the myopic night prices over `m` nights starting at this date (missing nights contribute 0 and disqualify `m`) minus `0.5 * nightly` for each orphan night the choice would leave that is shorter than `m`.

Choose `m*` with the highest value per night. Set `recommended_min_stay = m*`. Adjust the anchor night’s pre-guardrail price by

`(value(m*) - value(m_rule)) / m*`

capped at ±8% of the myopic price.

Reason code `stay_value`. Dollars: that adjustment.

Failure: fighting the orphan discount in `src/leakage`. The leakage rule still runs after this adjustment; it can reduce the price again. Document both reasons if both fire.

## M5 — portfolio

Twin pair: `summit_haus` and `overlook_ridge` only.

When pricing one twin, if the other is `available` that night:

`gap = abs(P_self - P_other) / max(P_other, 1)`

`λ = 0.15` if `gap < 0.10` else `0.05`

`price_ref' = price_ref * (1 - λ)`

Price the twins in sorted property-id order so Overlook sees Summit’s updated recommendation if both are in the same run. Cloud 9 has no pair.

Reason code `portfolio_cannibalization`. Dollars: optimum change from the `(1-λ)` factor.

Failure: both homes step down over successive days. Move caps limit the speed. λ is not increased to chase a score.

## Data and as-of rules

Every input above is known on `as_of`: resolved stays have `stay_date < as_of`, pacing rows have `as_of <= decision`, signals have `observed_at <= decision`. Thompson’s seed includes `as_of`, so a replay day does not depend on a later draw.

## Evaluation

See dossier 5. Losers are reported. Defaults stay off until the operator accepts a recommendation in the Phase 5 report.
