# engine vs comp_median decomposition — price_war

Seeds: 30 (1–30). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − comp_median): **-73,922**

## Night split

| outcome | nights | engine rev | comp_median rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 220.2 | 144,982 | 136,003 | 8,978 |
| neither_sold | 127.5 | 0 | 0 | 0 |
| only_comp_median_sold | 159.6 | 0 | 106,238 | -106,238 |
| only_engine_sold | 32.7 | 23,338 | 0 | 23,338 |

## By season

| season | engine rev | comp_median rev | delta | engine occ | comp_median occ | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 33,116 | 39,397 | -6,281 | 0.537 | 0.514 | 468 | 580 |
| peak_ski | 109,237 | 164,423 | -55,186 | 0.351 | 0.765 | 968 | 670 |
| shoulder_spring | 25,967 | 38,422 | -12,455 | 0.797 | 0.764 | 375 | 578 |

## By property

| property | engine rev | comp_median rev | delta | engine occ | comp_median occ | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 34,411 | 80,310 | -45,898 | 0.321 | 0.700 | 596 | 638 |
| overlook_ridge | 53,883 | 80,886 | -27,003 | 0.447 | 0.705 | 669 | 637 |
| summit_haus | 80,025 | 81,046 | -1,021 | 0.637 | 0.706 | 697 | 638 |

## By lead bucket

| lead_bucket | engine rev | comp_median rev | delta | engine nights | comp_median nights | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 13,104 | 13,599 | -495 | 22.500 | 22.830 | 582 | 596 |
| 121+ | 586 | 1,207 | -620 | 1.470 | 2.000 | 400 | 603 |
| 22-60 | 74,328 | 106,604 | -32,276 | 97.900 | 163.070 | 759 | 654 |
| 61-120 | 38,590 | 76,829 | -38,238 | 64.400 | 120.630 | 599 | 637 |
| 8-21 | 41,710 | 44,003 | -2,293 | 66.670 | 71.300 | 626 | 617 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---|
| early_winter | 55207 | 0.0% | 18.2% | clamped_decrease=166, clamped_increase=180, none=50281, sanity_floor=4580 |
| peak_ski | 789552 | 20.7% | 0.0% | clamped_decrease=19, clamped_increase=3138, none=715452, peak_blackout=70910, sanity_floor=33 |
| shoulder_spring | 280420 | 0.0% | 22.2% | none=280420 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| clamped_decrease | 0.2 | 119 | 0.0% |
| clamped_increase | 0.4 | 166 | 0.0% |
| none | 232.3 | 153,189 | 19.2% |
| peak_blackout | 12.8 | 12,194 | 1.6% |
| sanity_floor | 7.2 | 2,652 | 0.0% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 168319.33,
    "database_mean": 168319.33,
    "difference": 0.0
  },
  "comp_median": {
    "scoreboard_mean": 242241.41,
    "database_mean": 242241.41,
    "difference": 0.0
  }
}
```
