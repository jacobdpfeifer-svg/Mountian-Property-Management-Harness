# engine vs flat decomposition — normal

Seeds: 5 (1–5). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − flat): **-85,926**

## Night split

| outcome | nights | engine rev | flat rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 207.4 | 139,547 | 163,560 | -24,013 |
| neither_sold | 156.8 | 0 | 0 | 0 |
| only_engine_sold | 57.8 | 41,707 | 0 | 41,707 |
| only_flat_sold | 118.0 | 0 | 103,620 | -103,620 |

## By season

| season | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 35,869 | 47,400 | -11,531 | 0.568 | 0.479 | 478 | 750 |
| peak_ski | 120,204 | 177,660 | -57,456 | 0.384 | 0.615 | 976 | 900 |
| shoulder_spring | 25,181 | 42,120 | -16,939 | 0.770 | 0.745 | 376 | 650 |

## By property

| property | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 35,497 | 91,310 | -55,813 | 0.331 | 0.614 | 596 | 826 |
| overlook_ridge | 66,522 | 87,920 | -21,398 | 0.516 | 0.597 | 717 | 819 |
| summit_haus | 79,235 | 87,950 | -8,715 | 0.627 | 0.597 | 702 | 819 |

## By lead bucket

| lead_bucket | engine rev | flat rev | delta | engine nights | flat nights | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 19,826 | 17,980 | 1,846 | 30.400 | 22.800 | 652 | 789 |
| 121+ | 1,875 | 2,970 | -1,095 | 3.000 | 3.800 | 625 | 782 |
| 22-60 | 77,485 | 126,010 | -48,525 | 97.800 | 147.000 | 792 | 857 |
| 61-120 | 44,408 | 60,840 | -16,432 | 74.600 | 78.600 | 595 | 774 |
| 8-21 | 37,660 | 59,380 | -21,720 | 59.400 | 73.200 | 634 | 811 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---|
| early_winter | 8966 | 0.0% | 20.1% | clamped_decrease=18, clamped_increase=16, none=8087, sanity_floor=845 |
| peak_ski | 129382 | 19.8% | 0.0% | clamped_increase=532, none=117592, peak_blackout=11252, sanity_floor=6 |
| shoulder_spring | 44220 | 0.0% | 23.2% | none=44220 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| clamped_decrease | 0.2 | 74 | 0.0% |
| none | 242.2 | 162,866 | 18.9% |
| peak_blackout | 16.4 | 15,946 | 0.0% |
| sanity_floor | 6.4 | 2,368 | 0.0% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 181254.0,
    "database_mean": 181254.0,
    "difference": 0.0
  },
  "flat": {
    "scoreboard_mean": 267180.0,
    "database_mean": 267180.0,
    "difference": 0.0
  }
}
```
