# engine vs flat decomposition — normal

Seeds: 5 (1–5). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − flat): **-20,336**

Ceiling/floor tolerance: 1% of the bound. "Model ≥ ceiling" is the share of recommendations whose model price was already at or above the ceiling, i.e. the ceiling, not the demand model, set the price.

## Night split

| outcome | nights | engine rev | flat rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 256.4 | 217,018 | 208,160 | 8,858 |
| neither_sold | 180.8 | 0 | 0 | 0 |
| only_engine_sold | 33.8 | 29,826 | 0 | 29,826 |
| only_flat_sold | 69.0 | 0 | 59,020 | -59,020 |

## By season

| season | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 45,126 | 47,400 | -2,274 | 0.433 | 0.479 | 789 | 750 |
| peak_ski | 158,382 | 177,660 | -19,278 | 0.524 | 0.615 | 942 | 900 |
| shoulder_spring | 43,336 | 42,120 | 1,216 | 0.745 | 0.745 | 669 | 650 |

## By property

| property | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 72,356 | 91,310 | -18,954 | 0.431 | 0.614 | 932 | 826 |
| overlook_ridge | 90,082 | 87,920 | 2,162 | 0.594 | 0.597 | 842 | 819 |
| summit_haus | 84,406 | 87,950 | -3,544 | 0.587 | 0.597 | 799 | 819 |

## By lead bucket

| lead_bucket | engine rev | flat rev | delta | engine nights | flat nights | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 24,798 | 17,980 | 6,818 | 29.200 | 22.800 | 849 | 789 |
| 121+ | 3,204 | 2,970 | 234 | 3.800 | 3.800 | 843 | 782 |
| 22-60 | 109,884 | 126,010 | -16,126 | 123.600 | 147.000 | 889 | 857 |
| 61-120 | 58,130 | 60,840 | -2,710 | 73.800 | 78.600 | 788 | 774 |
| 8-21 | 50,828 | 59,380 | -8,552 | 59.800 | 73.200 | 850 | 811 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | model ≥ ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---:|---|
| early_winter | 10721 | 4.7% | 5.2% | 0.0% | clamped_increase=132, none=10589 |
| peak_ski | 120209 | 87.1% | 100.0% | 0.0% | clamped_increase=61, none=109941, peak_blackout=10207 |
| shoulder_spring | 46694 | 0.0% | 0.0% | 0.0% | clamped_increase=187, none=46507 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| none | 265.6 | 223,837 | 53.6% |
| peak_blackout | 24.6 | 23,007 | 69.9% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 246843.57,
    "database_mean": 246843.57,
    "difference": 0.0
  },
  "flat": {
    "scoreboard_mean": 267180.0,
    "database_mean": 267180.0,
    "difference": 0.0
  }
}
```
