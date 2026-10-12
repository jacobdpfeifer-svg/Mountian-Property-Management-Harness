# engine vs flat decomposition — normal

Seeds: 30 (1–30). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − flat): **-93,012**

## Night split

| outcome | nights | engine rev | flat rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 197.6 | 131,969 | 155,685 | -23,716 |
| neither_sold | 173.0 | 0 | 0 | 0 |
| only_engine_sold | 52.3 | 33,770 | 0 | 33,770 |
| only_flat_sold | 117.1 | 0 | 103,065 | -103,065 |

## By season

| season | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 32,290 | 41,900 | -9,610 | 0.530 | 0.423 | 462 | 750 |
| peak_ski | 107,739 | 174,990 | -67,251 | 0.346 | 0.606 | 969 | 900 |
| shoulder_spring | 25,709 | 41,860 | -16,151 | 0.790 | 0.740 | 374 | 650 |

## By property

| property | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 34,191 | 86,625 | -52,434 | 0.317 | 0.584 | 598 | 824 |
| overlook_ridge | 52,436 | 86,632 | -34,196 | 0.434 | 0.584 | 671 | 824 |
| summit_haus | 79,111 | 85,493 | -6,382 | 0.637 | 0.580 | 690 | 819 |

## By lead bucket

| lead_bucket | engine rev | flat rev | delta | engine nights | flat nights | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 13,286 | 19,287 | -6,001 | 22.970 | 23.830 | 578 | 809 |
| 121+ | 965 | 1,363 | -398 | 1.830 | 1.870 | 527 | 730 |
| 22-60 | 74,529 | 118,995 | -44,466 | 97.470 | 139.570 | 765 | 853 |
| 61-120 | 41,403 | 63,323 | -21,920 | 68.370 | 80.770 | 606 | 784 |
| 8-21 | 35,554 | 55,782 | -20,227 | 59.270 | 68.670 | 600 | 812 |
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
  "flat": {
    "scoreboard_mean": 258750.0,
    "database_mean": 258750.0,
    "difference": 0.0
  }
}
```
