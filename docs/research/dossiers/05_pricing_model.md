# Dossier 5 — A pricing model for thin luxury mountain inventory

Date: 2026-09-29
Access date for web sources: 2026-09-29

## What the engine does now

Linear demand `p(book|P) = p_ref * (1 + β * (P/P_ref - 1))`, clamped. The unconstrained optimum is `P* = P_ref * (β - 1) / (2β)`. For every `|β| < 1` the optimum is above any reasonable price, so the grid search sits on the ceiling. Peak β is the constant −0.65 (`config/policies/default.yaml`). `p_ref` scales probability and cancels out of `P*`. Pacing can multiply β by 1.3, to −0.845, which is still inelastic. Nothing updates β from bookings (audit M1).

## Comparison at our sample size

| Approach | Identified with ~50 stays? | Failure mode | Use |
|---|---|---|---|
| Keep seasonal constants | Yes, it is not estimated | Peak nights go to the ceiling. Closed-loop regret about 45% weekly on L1 (audit). | Baseline. |
| Hierarchical Bayes on β, prior = those constants, pooled across homes | The posterior stays on the prior until prices actually vary. Exploration inside move caps is required. | A bad early sample, or exploring on a holiday, gives away revenue. Blackout nights are excluded. | **M1.** |
| Shift the reference price with demand | Yes, it does not need a new elasticity | Double-counting snow that already moves the ceiling | **M2.** Small weights. |
| Finite-horizon bid prices | Lead buckets exist (`_lead_observations`) but counts are thin | Garbage continuation value if the bucket rate is the shrunk prior | **M3.** Shrink hard. |
| Stay / min-stay optimization | Orphan rules already exist | A joint search over LOS and price is easy to overfit | **M4.** Discrete LOS in {2,3,4,5,7}. |
| Twin cannibalization | The two Northwoods homes are the identifying pair. Cloud 9 is not a twin. | Pricing them as one listing when a date is sold on only one | **M5.** |
| Segment WTP mixture | Shares are mostly assumed (dossier 1) | Fitting shares to 47 stays | Simulator now. Engine only behind M2’s demand shift, not a per-guest price. |

PriceLabs’ public algorithm already does per-date sensitivity, lead-time value, and dynamic min-stay (dossier 4). The parts that are not “a generalized tool with a mountain skin” are: learning β from **our** as-of fills under move caps, refusing an inelastic peak night that is behind pace inside 21 days, and a cannibalization term for two specific twins. Those are the pieces to test. They are not novel as mathematics. They are novel here only as a closed loop the current code does not have.

## Equations (implemented in MODEL_SPEC.md)

M1. Prior `β_s` from policy. After resolved nights, a shrunk slope:

`β_post = (κ β_prior + n β_hat) / (κ + n)`

`β_hat` is the slope implied by book rates above versus below the median as-of price in that season, clipped to [−2.5, −0.3]. `κ = 40` so 47 mixed-season stays barely move the prior. Thompson sampling draws `β ~ Normal(β_post, σ)` with `σ = 0.35 / sqrt(κ+n)`, only when the night is not in peak blackout, and the resulting price is still guardrailed. Interim guard, same flag: if season is peak, `pacing_ratio < 0.70`, and lead ≤ 21, use `min(β, -1.05)`.

M2. `price_ref' = price_ref * (1 + a_pace (pace - 1) + a_sqi (sqi - 1) + a_event)`. Weights start at 0.15, 0.10, 0.10 and are clipped so the factor stays in [0.85, 1.20]. The linear argmax then moves. Dollar reason = new optimum minus old optimum, before guardrails.

M3. Continuation `C(lead)` = (empirical lead-bucket book rate) × (current floor+ceiling)/2, shrunk toward 0 with k=12. Choose the grid price maximizing `p(P) * P + (1 - p(P)) * C`. This is one-step lookahead, not a full dynamic program. A full DP over 180 nights is not identified and is slow.

M4. For each candidate min-stay m in the policy table, score the stay that starts on this night with length m: sum of night prices minus an orphan penalty if a gap shorter than m would be left on either side. Pick m with the best score. Price of the anchor night moves by the difference versus m = current rule. Reason code carries that dollar gap.

M5. If the twin is free for the same night and neither is booked, multiply this home’s `p_ref` by `(1 - λ)`, `λ = 0.15` when the absolute price gap is under 10%, else `λ = 0.05`. Cloud 9 is untouched. This is a demand shift, so it only changes the optimum if M2 is also on **or** if M5 itself shifts `price_ref`. M5 shifts `price_ref` by `(1 - λ)` as well, so it can move price with M2 off. Document that. Both flags default off.

## Evaluation ladder

Unit tests, then replay (early and clean, per-decision and deduplicated), then non-held-out simulator scenarios, then held-out once. A win: paired realized-revenue difference versus the flag-off engine on `normal`, bootstrap 95% interval excludes zero, no stress scenario loses more than 5% of paired revenue, guardrail violations stay 0, replay Brier does not worsen by more than 0.02. Do not turn the flag on in `default.yaml`.

## Data the estimators need

As-of listed price, booking indicator known on the decision day, season, lead bucket, pacing ratio, twin availability. All of those exist. Elasticity still needs **price variation**. The peak policy does not create any. Thompson sampling inside caps is the variation. Without it M1 reports the prior and changes nothing, which is the correct thin-data behavior.

## Failure modes

- Exploring into a holiday that would have filled at the ceiling.
- M2 and the ceiling both adding a snow premium.
- M4 lengthening min-stay on a gap the orphan rule already discounts.
- M5 discounting both twins so the portfolio race-to-the-bottom. The factor only applies to the home being priced; run twins in property-id order and let the second see the first’s new price. Still a heuristic.

## What to do next

Implement behind flags. Do not retune κ or λ to a score.

## Open questions

- Is a 5% stress loss the right “material” bar? It is the bar used in Phase 5 unless the operator says otherwise.
- Should the interim peak guard be always on, even with the flag off? The plan keeps it on the flag so flag-off stays comparable. The unsafe peak behavior remains until the operator enables the flag.
