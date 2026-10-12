# Candidate policy trials (YAML only)

Simulated shopper-world revenue. Not realized revenue. Intervals are not family-wise adjusted. `config/policies/default.yaml` was not edited. Every `models.*.enabled` stayed false. Guesty was not touched.

Copies live at `~/wp-price-runs/market_sim/baseline_79dae5d/candidates/`. Screens: seeds 1–5, engine only, paired to the baseline scoreboard. Confirmation of the promoted candidate used seeds 1–30 and was graded on seeds 6–30.

## What was tried

| name | YAML change | screen vs baseline engine on `normal` | promoted? |
|---|---|---|---|
| `peak_more_elastic` | `peak_ski` elasticity −0.65 → −1.20 | −$1,797 (2/5) | no — failed `normal` |
| `shoulder_off_floor` | `early_winter`/`shoulder_*` → −1.10 | +$4,923 (5/5) | yes |
| `lower_peak_ceiling` | `ceiling.percentile` 0.90 → 0.80 | +$112 (5/5) | no — near-zero; `regime_change` −$6 |

## Screen: `peak_more_elastic` (lost)

Targets peak volume. On seeds 1–5 it **lost** to the current engine on `normal` (−$1,797). It did help several stress winters, including `pandemic_collapse` (+$24,640) and `den_capacity_cut` (+$14,796), and did not make `price_war` worse (+$6,171). Promotion requires a `normal` win. Not confirmed.

Engine − baseline_engine (seeds 1–5):

| scenario | held out | mean | median | min | max | nonnegative | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | -1,797 | -2,930 | -13,710 | 10,440 | 2/5 | -8,783 to 5,012 |
| price_war |  | 6,171 | 4,725 | -9,580 | 18,275 | 3/5 | -2,969 to 15,184 |
| holiday_shift | yes | 8,129 | 11,490 | -3,852 | 20,490 | 3/5 | -349 to 15,848 |
| den_capacity_cut | yes | 14,796 | 8,285 | 585 | 41,420 | 5/5 | 3,019 to 29,143 |
| regime_change | yes | 8,775 | 10,890 | -14,085 | 28,510 | 3/5 | -4,126 to 21,676 |
| pandemic_collapse | yes | 24,640 | 26,280 | 13,543 | 30,395 | 5/5 | 18,750 to 28,722 |
| drought |  | 30,219 | 27,100 | 21,025 | 48,250 | 5/5 | 23,559 to 39,894 |
| early_closure |  | 6,821 | -570 | -18,555 | 35,535 | 2/5 | -10,918 to 24,860 |
| i70_closure |  | 14,609 | 9,565 | 5,105 | 32,170 | 5/5 | 6,799 to 24,142 |
| late_opening |  | 28,128 | 29,220 | 19,605 | 36,040 | 5/5 | 22,918 to 32,972 |
| recession |  | 12,543 | 14,987 | -8,532 | 36,095 | 4/5 | -1,086 to 25,690 |
| record_snow |  | 2,287 | -1,870 | -11,245 | 20,770 | 2/5 | -9,325 to 13,914 |
| scrape_outage |  | 20,073 | 24,385 | 4,635 | 30,710 | 5/5 | 10,908 to 27,799 |
| stale_pms |  | 15,857 | 11,015 | -2,095 | 41,785 | 4/5 | 3,153 to 30,787 |
| supply_surge |  | 9,397 | 14,899 | -5,240 | 16,355 | 4/5 | 1,310 to 15,545 |

## Screen: `shoulder_off_floor` (promoted)

Targets floor-pinned underpricing on early winter and shoulder. Screen beat the current engine on `normal` and on all four held-out winters; `price_war` and `pandemic_collapse` were not worse.

YAML:

```
booking_probability.elasticity_by_season:
  early_winter:    -1.10   # was -1.35
  shoulder_spring: -1.10   # was -1.70
  shoulder_fall:   -1.10   # was -1.70
```

Engine − baseline_engine (seeds 1–5):

| scenario | held out | mean | median | min | max | nonnegative | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | 4,923 | 5,050 | 2,385 | 7,010 | 5/5 | 3,584 to 6,226 |
| price_war |  | 6,666 | 5,735 | 5,230 | 9,045 | 5/5 | 5,346 to 8,091 |
| holiday_shift | yes | 5,231 | 5,085 | 1,160 | 8,214 | 5/5 | 3,153 to 7,308 |
| den_capacity_cut | yes | 5,270 | 5,665 | 2,405 | 7,675 | 5/5 | 3,797 to 6,743 |
| regime_change | yes | 6,839 | 7,060 | 4,370 | 8,195 | 5/5 | 5,536 to 7,741 |
| pandemic_collapse | yes | 917 | 1,550 | -3,035 | 2,940 | 4/5 | -1,195 to 2,357 |
| drought |  | 3,041 | 3,145 | -2,620 | 6,520 | 4/5 | 23 to 5,787 |
| early_closure |  | 4,188 | 3,630 | -2,165 | 8,625 | 4/5 | 868 to 7,360 |
| i70_closure |  | 1,856 | 3,555 | -6,180 | 4,575 | 4/5 | -2,219 to 4,302 |
| late_opening |  | 3,529 | 2,760 | -95 | 8,525 | 4/5 | 852 to 6,406 |
| recession |  | 4,204 | 3,210 | 2,765 | 7,245 | 5/5 | 2,978 to 5,604 |
| record_snow |  | 6,143 | 4,645 | 2,440 | 12,750 | 5/5 | 3,640 to 9,508 |
| scrape_outage |  | 1,621 | 2,825 | -6,205 | 5,805 | 4/5 | -2,587 to 4,520 |
| stale_pms |  | 5,715 | 7,060 | 2,355 | 7,820 | 5/5 | 3,681 to 7,406 |
| supply_surge |  | 4,078 | 2,835 | 5 | 9,730 | 5/5 | 915 to 7,241 |

## Screen: `lower_peak_ceiling` (lost)

Targets a high history ceiling while only ~20% of peak recs sit at that ceiling. Effect is essentially zero (median $0 on most scenarios). `regime_change` mean −$6. Not confirmed.

Engine − baseline_engine (seeds 1–5):

| scenario | held out | mean | median | min | max | nonnegative | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | 112 | 0 | 0 | 560 | 5/5 | 0 to 336 |
| price_war |  | 5 | 0 | 0 | 25 | 5/5 | 0 to 15 |
| holiday_shift | yes | 7 | 0 | 0 | 25 | 5/5 | 0 to 17 |
| den_capacity_cut | yes | 0 | 0 | 0 | 0 | 5/5 | 0 to 0 |
| regime_change | yes | -6 | 0 | -30 | 0 | 4/5 | -18 to 0 |
| pandemic_collapse | yes | 0 | 0 | 0 | 0 | 5/5 | 0 to 0 |
| drought |  | -7 | 0 | -35 | 0 | 4/5 | -21 to 0 |
| early_closure |  | -3 | 0 | -15 | 0 | 4/5 | -9 to 0 |
| i70_closure |  | 0 | 0 | 0 | 0 | 5/5 | 0 to 0 |
| late_opening |  | 0 | 0 | 0 | 0 | 5/5 | 0 to 0 |
| recession |  | -10 | 0 | -30 | 10 | 3/5 | -24 to 4 |
| record_snow |  | 25 | 0 | -5 | 99 | 4/5 | -2 to 64 |
| scrape_outage |  | -3 | 0 | -25 | 10 | 4/5 | -15 to 6 |
| stale_pms |  | 6 | 0 | 0 | 20 | 5/5 | 0 to 14 |
| supply_surge |  | 896 | 0 | 0 | 4,480 | 5/5 | 0 to 2,688 |

## Confirmation: `shoulder_off_floor` (seeds 6–30)

450 engine jobs, exit 0, `~/wp-price-runs/market_sim/baseline_79dae5d/confirm_shoulder_off_floor/`. Audit `--seeds-from 6` complete. Seeds 1–5, which picked it, are excluded from the grade.

Versus the current engine it earns about **+$5,700** on `normal` (24/25 seeds; interval $4,542 to $6,941). It also beats the current engine on all four held-out winters’ means; `pandemic_collapse` is only +$86 and the interval includes zero. `price_war` +$5,005 (21/25). It still loses to the **flat** rate by about **−$89,000** on `normal` (0/25 seeds).

### Engine − baseline_engine (seeds 6–30)

| scenario | held out | mean | median | min | max | nonnegative | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | 5,697 | 5,525 | -240 | 12,855 | 24/25 | 4,542 to 6,941 |
| price_war |  | 5,005 | 6,350 | -2,675 | 12,635 | 21/25 | 3,503 to 6,448 |
| holiday_shift | yes | 4,550 | 5,170 | -6,645 | 17,290 | 21/25 | 2,536 to 6,546 |
| den_capacity_cut | yes | 5,090 | 6,090 | -2,610 | 10,962 | 22/25 | 3,782 to 6,532 |
| regime_change | yes | 4,668 | 5,790 | -16,765 | 14,740 | 22/25 | 2,213 to 6,669 |
| pandemic_collapse | yes | 86 | 45 | -3,005 | 4,300 | 13/25 | -607 to 814 |
| drought |  | 4,376 | 4,760 | -4,390 | 10,150 | 24/25 | 2,936 to 5,685 |
| early_closure |  | 4,883 | 4,270 | -3,140 | 12,290 | 23/25 | 3,509 to 6,240 |
| i70_closure |  | 4,313 | 3,300 | -270 | 13,795 | 24/25 | 3,013 to 5,671 |
| late_opening |  | 4,459 | 5,030 | -1,165 | 9,540 | 23/25 | 3,339 to 5,539 |
| recession |  | 4,255 | 4,015 | -2,280 | 12,550 | 22/25 | 2,848 to 5,642 |
| record_snow |  | 4,886 | 4,895 | -4,960 | 10,950 | 22/25 | 3,320 to 6,409 |
| scrape_outage |  | 3,731 | 3,890 | -940 | 9,820 | 23/25 | 2,649 to 4,816 |
| stale_pms |  | 4,022 | 4,345 | -4,545 | 10,835 | 22/25 | 2,624 to 5,397 |
| supply_surge |  | 4,007 | 3,815 | -3,380 | 9,720 | 22/25 | 2,701 to 5,264 |

Descriptive: mean beats the current engine on 15 of 15 scenarios. Mean beats flat on 0 of 15.

### Engine − flat (seeds 6–30)

| scenario | held out | mean | median | min | max | nonnegative | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | -88,732 | -88,040 | -126,875 | -67,475 | 0/25 | -94,932 to -82,989 |
| price_war |  | -86,895 | -87,270 | -119,660 | -48,425 | 0/25 | -93,934 to -80,043 |
| holiday_shift | yes | -89,154 | -89,430 | -117,040 | -46,180 | 0/25 | -96,421 to -81,623 |
| den_capacity_cut | yes | -87,243 | -87,565 | -119,915 | -53,310 | 0/25 | -93,240 to -81,284 |
| regime_change | yes | -83,014 | -81,520 | -120,625 | -36,083 | 0/25 | -88,911 to -76,952 |
| pandemic_collapse | yes | -15,807 | -15,190 | -35,415 | -800 | 0/25 | -18,976 to -12,726 |
| drought |  | -88,598 | -90,165 | -136,225 | -51,780 | 0/25 | -95,333 to -82,206 |
| early_closure |  | -85,111 | -83,100 | -124,300 | -52,230 | 0/25 | -91,502 to -78,416 |
| i70_closure |  | -84,379 | -87,495 | -126,020 | -34,386 | 0/25 | -91,183 to -77,308 |
| late_opening |  | -87,615 | -90,020 | -105,245 | -58,945 | 0/25 | -92,703 to -82,655 |
| recession |  | -81,618 | -83,100 | -123,065 | -47,325 | 0/25 | -88,638 to -74,822 |
| record_snow |  | -83,829 | -82,925 | -118,155 | -60,120 | 0/25 | -89,981 to -77,389 |
| scrape_outage |  | -85,863 | -84,435 | -119,715 | -61,910 | 0/25 | -91,958 to -79,908 |
| stale_pms |  | -87,876 | -87,120 | -109,105 | -64,821 | 0/25 | -92,792 to -82,982 |
| supply_surge |  | -84,448 | -83,555 | -126,835 | -57,200 | 0/25 | -89,770 to -79,469 |

## Risks

- Making shoulder demand less elastic raises simulated ADR; if real guests need cheap shoulder nights, occupancy can fall.
- Peak volume (Cloud 9, 22–60 day lead) is still the large remaining gap versus flat. `peak_more_elastic` did not help `normal` on the screen.
- `lower_peak_ceiling` barely moved prices — a percentile tweak is not a substitute for whatever sets Cloud 9’s peak listed band.
- Production `default.yaml` is unchanged. Shipping this candidate is an owner decision.

## Recommendation

Do **not** copy `shoulder_off_floor` into `default.yaml` on this evidence alone. It is a small, consistent simulated improvement over the current engine and still far below the flat seasonal benchmark. Leave learning flags off.
