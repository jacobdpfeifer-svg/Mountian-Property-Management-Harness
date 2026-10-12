# engine vs comp_median decomposition — holiday_shift

Seeds: 30 (1–30). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − comp_median): **-86,652**

## Night split

| outcome | nights | engine rev | comp_median rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 218.7 | 145,059 | 144,970 | 88 |
| neither_sold | 124.0 | 0 | 0 | 0 |
| only_comp_median_sold | 159.3 | 0 | 113,161 | -113,161 |
| only_engine_sold | 38.0 | 26,421 | 0 | 26,421 |

## By season

| season | engine rev | comp_median rev | delta | engine occ | comp_median occ | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 31,125 | 39,182 | -8,056 | 0.515 | 0.474 | 458 | 626 |
| peak_ski | 113,890 | 176,701 | -62,812 | 0.367 | 0.768 | 967 | 717 |
| shoulder_spring | 26,464 | 42,248 | -15,784 | 0.817 | 0.793 | 373 | 613 |

## By property

| property | engine rev | comp_median rev | delta | engine occ | comp_median occ | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 35,527 | 83,756 | -48,229 | 0.321 | 0.681 | 614 | 683 |
| overlook_ridge | 51,842 | 86,585 | -34,743 | 0.434 | 0.704 | 663 | 683 |
| summit_haus | 84,110 | 87,790 | -3,680 | 0.671 | 0.715 | 697 | 682 |

## By lead bucket

| lead_bucket | engine rev | comp_median rev | delta | engine nights | comp_median nights | engine ADR | comp_median ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 12,984 | 13,281 | -297 | 22.270 | 20.700 | 583 | 642 |
| 121+ | 793 | 1,323 | -530 | 1.800 | 2.030 | 440 | 651 |
| 22-60 | 78,509 | 120,254 | -41,745 | 102.030 | 172.100 | 769 | 699 |
| 61-120 | 40,370 | 77,218 | -36,849 | 68.730 | 113.630 | 587 | 680 |
| 8-21 | 38,823 | 46,054 | -7,231 | 61.900 | 69.570 | 627 | 662 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---|
| early_winter | 56371 | 0.0% | 18.4% | clamped_decrease=61, clamped_increase=66, none=50879, sanity_floor=5365 |
| peak_ski | 783405 | 19.9% | 0.0% | clamped_increase=3119, none=710611, peak_blackout=69652, sanity_floor=23 |
| shoulder_spring | 272012 | 0.0% | 23.6% | none=272012 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| none | 235.8 | 155,542 | 19.3% |
| peak_blackout | 14.2 | 13,446 | 1.7% |
| sanity_floor | 6.7 | 2,491 | 0.0% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 171479.23,
    "database_mean": 171479.23,
    "difference": 0.0
  },
  "comp_median": {
    "scoreboard_mean": 258131.08,
    "database_mean": 258131.08,
    "difference": -0.0
  }
}
```
