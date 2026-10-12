# engine vs flat decomposition — holiday_shift

Seeds: 30 (1–30). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − flat): **-94,861**

## Night split

| outcome | nights | engine rev | flat rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 204.0 | 136,774 | 161,017 | -24,243 |
| neither_sold | 163.4 | 0 | 0 | 0 |
| only_engine_sold | 52.8 | 34,705 | 0 | 34,705 |
| only_flat_sold | 119.9 | 0 | 105,323 | -105,323 |

## By season

| season | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 31,125 | 40,425 | -9,300 | 0.515 | 0.408 | 458 | 750 |
| peak_ski | 113,890 | 181,650 | -67,760 | 0.367 | 0.629 | 967 | 900 |
| shoulder_spring | 26,464 | 44,265 | -17,801 | 0.817 | 0.783 | 373 | 650 |

## By property

| property | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 35,527 | 86,393 | -50,866 | 0.321 | 0.582 | 614 | 824 |
| overlook_ridge | 51,842 | 90,330 | -38,488 | 0.434 | 0.610 | 663 | 822 |
| summit_haus | 84,110 | 89,617 | -5,507 | 0.671 | 0.607 | 697 | 821 |

## By lead bucket

| lead_bucket | engine rev | flat rev | delta | engine nights | flat nights | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 12,984 | 17,490 | -4,506 | 22.270 | 21.600 | 583 | 810 |
| 121+ | 793 | 985 | -192 | 1.800 | 1.400 | 440 | 704 |
| 22-60 | 78,509 | 127,440 | -48,931 | 102.030 | 149.800 | 769 | 851 |
| 61-120 | 40,370 | 63,303 | -22,934 | 68.730 | 81.130 | 587 | 780 |
| 8-21 | 38,823 | 57,122 | -18,298 | 61.900 | 69.900 | 627 | 817 |
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
  "flat": {
    "scoreboard_mean": 266340.0,
    "database_mean": 266340.0,
    "difference": 0.0
  }
}
```
