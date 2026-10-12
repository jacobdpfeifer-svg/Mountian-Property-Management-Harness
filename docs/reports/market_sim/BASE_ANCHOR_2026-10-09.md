# Seasonal base anchor — 2026-10-09

**Candidate:** `config/policies/candidates/seasonal_base_anchor_full_shoulder.yaml`
**Commit:** `79dae5d` (dirty working tree; promoted `default.yaml` with Cloud 9 / Overlook caps)
**Artifact roots:** `~/wp-price-runs/market_sim/screen_base_anchor_79dae5d/` (screen), `~/wp-price-runs/market_sim/confirm_base_anchor_79dae5d/` (confirmation)
**Reference:** promoted default, `~/wp-price-runs/market_sim/post_promote_79dae5d/default_*_1_30`. Flat: `baseline_79dae5d`.

Simulated shopper revenue only. Not realized revenue. `default.yaml` and `calibration.yaml` were not edited. Guesty was not touched.

## Mechanism

Both the ceiling (p90 of booked prices) and the demand reference `price_ref` (mean of past booked/listed prices) are read from this season's own nights. With linear demand the RevPAN optimum is `price_ref × (β−1)/(2β)`: 0.79× at β=−1.70 and 0.73× at β=−2.21 (pacing behind). Each sale lowers the next reference and the next p90, so early-winter and shoulder prices walk down to the floor.

Evidence, post-promote diagnostic DBs, `normal`, seeds 1–6, engine − flat: early winter −$12.0k (ADR $477 vs $750), shoulder −$16.5k (ADR $375 vs $650) at *higher* engine occupancy; 20–23% of those recommendations at the floor. Summit Haus April: ceiling "$340 via p90_season (n=13)", listed $330–$340, floor $330, base × 0.85 = $674.

## Change

`seasonal_base_anchor` (off unless enabled): `price_ref ≥ price_ref_min_ratio × base_ceiling_rate × season multiplier`; ceiling ≥ `ceiling_min_ratio × base × multiplier`, applied before the property premium and property-season caps so those still bind. Code: `src/ceiling/__init__.py` (`seasonal_base_floor`), `src/bookprob/__init__.py`. Tests: `tests/test_seasonal_base_anchor.py`. Full suite 446 passed.

## Screen (`normal`, seeds 1–5, vs promoted default)

| candidate | Δ revenue | wins | engine − flat |
|---|---:|---:|---:|
| promoted default | — | — | −46,680 |
| `shoulder_off_floor_promoted` (elasticity only) | +7,885 | 5/5 | −38,795 |
| `seasonal_base_anchor` (0.90 / 1.00) | +18,693 | 5/5 | −27,987 |
| `seasonal_base_anchor_shoulder` (0.90 / 1.00 + elasticity) | +24,432 | 5/5 | −22,247 |
| **`seasonal_base_anchor_full_shoulder`** (1.00 / 1.00 + elasticity) | **+26,343** | 5/5 | **−20,336** |

The last row was picked for confirmation before seeds 6–30 were run.

## Confirmation (seeds 6–30, candidate − promoted default)

`scripts/confirm_base_anchor_market_sim.sh`. All six audits `complete: true`.

| scenario | held out | mean Δ | 95% CI | wins/25 | candidate − flat |
|---|---|---:|---|---:|---:|
| normal | | +23,296 | +19,551 to +27,057 | 25 | −22,680 |
| price_war | | +23,339 | +20,046 to +27,035 | 25 | −21,783 |
| holiday_shift | yes | +20,708 | +17,403 to +23,651 | 25 | −23,970 |
| den_capacity_cut | yes | +22,869 | +19,480 to +25,987 | 25 | −21,911 |
| regime_change | yes | +18,904 | +14,026 to +23,471 | 23 | −24,397 |
| pandemic_collapse | yes | +1,693 | −527 to +4,130 | 14 | −5,870 |

Not family-wise adjusted. The gap to flat on `normal` falls from about −$46k to about −$23k. The engine still does not beat flat.

## Risks before production

- The guard trusts `base_ceiling_rate` (Summit $793, Overlook $916, Cloud 9 $1,035) and the season multipliers. With real Guesty history, any season whose realised prices sit below base × multiplier gets lifted. Those base rates need owner confirmation as true seasonal expectations.
- Occupancy falls (screen mean 0.537 vs 0.575) while ADR rises ($850 vs $709). Real shoulder guests may be more price-sensitive than the simulated ones.
- `pandemic_collapse` is flat (interval includes zero).
- Remaining gap: peak (~−$17k on the diagnostic sample) is untouched by this change.

## Decision

Promote for owner review. Do not copy into `default.yaml` without owner approval of the guard and of the base rates.
