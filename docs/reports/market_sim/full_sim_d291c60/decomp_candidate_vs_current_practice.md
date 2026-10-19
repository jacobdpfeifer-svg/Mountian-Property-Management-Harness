# engine vs current_practice decomposition — normal

Seeds: 5 (1–5). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − current_practice): **-30,719**

Ceiling/floor tolerance: 1% of the bound. "Model ≥ ceiling" is the share of recommendations whose model price was already at or above the ceiling, i.e. the ceiling, not the demand model, set the price.

## Night split

| outcome | nights | engine rev | current_practice rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 257.0 | 428,679 | 456,931 | -28,251 |
| neither_sold | 146.2 | 0 | 0 | 0 |
| only_current_practice_sold | 73.0 | 0 | 104,641 | -104,641 |
| only_engine_sold | 63.8 | 102,173 | 0 | 102,173 |

## By season

| season | engine rev | current_practice rev | delta | engine occ | current_practice occ | engine ADR | current_practice ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 49,928 | 46,866 | 3,062 | 0.429 | 0.517 | 882 | 687 |
| peak_ski | 453,165 | 489,158 | -35,992 | 0.688 | 0.678 | 2,052 | 2,246 |
| shoulder_spring | 27,759 | 25,547 | 2,212 | 0.499 | 0.506 | 640 | 581 |

## By property

| property | engine rev | current_practice rev | delta | engine occ | current_practice occ | engine ADR | current_practice ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 174,303 | 194,796 | -20,492 | 0.580 | 0.556 | 1,670 | 1,948 |
| overlook_ridge | 176,147 | 183,333 | -7,185 | 0.592 | 0.639 | 1,652 | 1,594 |
| summit_haus | 180,401 | 183,443 | -3,041 | 0.610 | 0.639 | 1,643 | 1,595 |

## By lead bucket

| lead_bucket | engine rev | current_practice rev | delta | engine nights | current_practice nights | engine ADR | current_practice ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 26,661 | 33,904 | -7,243 | 24.200 | 27.600 | 1,102 | 1,228 |
| 121+ | 624 | 646 | -22 | 1.000 | 1.200 | 624 | 538 |
| 22-60 | 262,415 | 285,266 | -22,851 | 136.400 | 149.400 | 1,924 | 1,909 |
| 61-120 | 119,102 | 139,297 | -20,195 | 74.800 | 79.800 | 1,592 | 1,746 |
| 8-21 | 122,050 | 102,458 | 19,592 | 84.400 | 72.000 | 1,446 | 1,423 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | model ≥ ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---:|---|
| early_winter | 10634 | 27.4% | 28.5% | 0.0% | clamped_decrease=92, clamped_increase=560, none=9982 |
| peak_ski | 102605 | 51.6% | 51.8% | 0.0% | clamped_decrease=4051, clamped_increase=7137, none=82825, peak_blackout=8349, sanity_ceiling=243 |
| shoulder_spring | 59411 | 9.0% | 9.3% | 0.0% | clamped_decrease=307, clamped_increase=1476, none=57628 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| clamped_decrease | 11.2 | 21,596 | 19.6% |
| clamped_increase | 15.2 | 27,492 | 27.6% |
| none | 262.6 | 407,433 | 31.3% |
| peak_blackout | 31.8 | 74,332 | 88.0% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 530852.36,
    "database_mean": 530852.36,
    "difference": 0.0
  },
  "current_practice": {
    "status": "scoreboard has 0 of 5 seeds"
  }
}
```
