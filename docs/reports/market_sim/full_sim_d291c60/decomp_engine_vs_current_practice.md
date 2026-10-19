# engine vs current_practice decomposition — normal

Seeds: 5 (1–5). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − current_practice): **-220,753**

Ceiling/floor tolerance: 1% of the bound. "Model ≥ ceiling" is the share of recommendations whose model price was already at or above the ceiling, i.e. the ceiling, not the demand model, set the price.

## Night split

| outcome | nights | engine rev | current_practice rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 282.4 | 257,145 | 481,518 | -224,373 |
| neither_sold | 109.4 | 0 | 0 | 0 |
| only_current_practice_sold | 47.6 | 0 | 80,053 | -80,053 |
| only_engine_sold | 100.6 | 83,673 | 0 | 83,673 |

## By season

| season | engine rev | current_practice rev | delta | engine occ | current_practice occ | engine ADR | current_practice ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 36,865 | 46,866 | -10,001 | 0.538 | 0.517 | 519 | 687 |
| peak_ski | 278,913 | 489,158 | -210,245 | 0.764 | 0.678 | 1,137 | 2,246 |
| shoulder_spring | 25,040 | 25,547 | -507 | 0.765 | 0.506 | 376 | 581 |

## By property

| property | engine rev | current_practice rev | delta | engine occ | current_practice occ | engine ADR | current_practice ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 111,168 | 194,796 | -83,628 | 0.722 | 0.556 | 855 | 1,948 |
| overlook_ridge | 94,570 | 183,333 | -88,763 | 0.696 | 0.639 | 755 | 1,594 |
| summit_haus | 135,080 | 183,443 | -48,363 | 0.710 | 0.639 | 1,057 | 1,595 |

## By lead bucket

| lead_bucket | engine rev | current_practice rev | delta | engine nights | current_practice nights | engine ADR | current_practice ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 16,809 | 33,904 | -17,095 | 25.800 | 27.600 | 652 | 1,228 |
| 121+ | 987 | 646 | 341 | 2.600 | 1.200 | 380 | 538 |
| 22-60 | 156,331 | 285,266 | -128,935 | 158.200 | 149.400 | 988 | 1,909 |
| 61-120 | 108,828 | 139,297 | -30,469 | 116.600 | 79.800 | 933 | 1,746 |
| 8-21 | 57,863 | 102,458 | -44,595 | 79.800 | 72.000 | 725 | 1,423 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | model ≥ ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---:|---|
| early_winter | 9562 | 0.6% | 0.0% | 8.3% | clamped_decrease=27, clamped_increase=27, none=7826, sanity_floor=1682 |
| peak_ski | 88758 | 79.1% | 86.2% | 0.0% | clamped_decrease=5265, clamped_increase=571, none=75342, peak_blackout=7525, sanity_floor=55 |
| shoulder_spring | 48826 | 0.0% | 0.0% | 23.8% | none=34127, sanity_floor=14699 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| clamped_decrease | 9.8 | 12,500 | 73.5% |
| clamped_increase | 1.0 | 1,012 | 0.0% |
| none | 302.6 | 273,086 | 54.6% |
| peak_blackout | 35.2 | 41,413 | 85.2% |
| sanity_floor | 34.4 | 12,807 | 0.0% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 340817.74,
    "database_mean": 340817.74,
    "difference": -0.0
  },
  "current_practice": {
    "scoreboard_mean": 561571.2,
    "database_mean": 561571.2,
    "difference": 0.0
  }
}
```
