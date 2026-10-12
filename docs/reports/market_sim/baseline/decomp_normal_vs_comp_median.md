# engine vs comp_median decomposition — normal

Seeds: 30 (1–30). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − comp_median): **-89,253**

## Night split

| outcome | nights | engine rev | comp_median rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 213.2 | 140,502 | 140,857 | -355 |
| neither_sold | 129.6 | 0 | 0 | 0 |
| only_comp_median_sold | 160.5 | 0 | 114,134 | -114,134 |
| only_engine_sold | 36.7 | 25,236 | 0 | 25,236 |

## By season

| season | engine rev | comp_median rev | delta | engine occ | comp_median occ | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 32,290 | 39,997 | -7,707 | 0.530 | 0.486 | 462 | 623 |
| peak_ski | 107,739 | 174,619 | -66,880 | 0.346 | 0.759 | 969 | 717 |
| shoulder_spring | 25,709 | 40,375 | -14,666 | 0.790 | 0.757 | 374 | 613 |

## By property

| property | engine rev | comp_median rev | delta | engine occ | comp_median occ | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 34,191 | 84,875 | -50,684 | 0.317 | 0.691 | 598 | 682 |
| overlook_ridge | 52,436 | 85,522 | -33,086 | 0.434 | 0.695 | 671 | 683 |
| summit_haus | 79,111 | 84,594 | -5,483 | 0.637 | 0.690 | 690 | 681 |

## By lead bucket

| lead_bucket | engine rev | comp_median rev | delta | engine nights | comp_median nights | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 13,286 | 14,192 | -906 | 22.970 | 22.230 | 578 | 638 |
| 121+ | 965 | 1,931 | -966 | 1.830 | 2.900 | 527 | 666 |
| 22-60 | 74,529 | 115,252 | -40,722 | 97.470 | 164.800 | 765 | 699 |
| 61-120 | 41,403 | 78,751 | -37,348 | 68.370 | 115.970 | 606 | 679 |
| 8-21 | 35,554 | 44,865 | -9,310 | 59.270 | 67.830 | 600 | 661 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---|
| early_winter | 56295 | 0.1% | 18.2% | clamped_decrease=90, clamped_increase=132, none=50626, sanity_floor=5447 |
| peak_ski | 785951 | 19.7% | 0.0% | clamped_increase=3126, none=713548, peak_blackout=69255, sanity_floor=22 |
| shoulder_spring | 279832 | 0.0% | 21.8% | none=279832 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| clamped_decrease | 0.1 | 52 | 0.0% |
| clamped_increase | 0.3 | 117 | 0.0% |
| none | 228.7 | 149,491 | 17.4% |
| peak_blackout | 14.2 | 13,649 | 1.6% |
| sanity_floor | 6.6 | 2,430 | 0.0% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 165738.38,
    "database_mean": 165738.38,
    "difference": 0.0
  },
  "comp_median": {
    "scoreboard_mean": 254991.27,
    "database_mean": 254991.27,
    "difference": 0.0
  }
}
```
