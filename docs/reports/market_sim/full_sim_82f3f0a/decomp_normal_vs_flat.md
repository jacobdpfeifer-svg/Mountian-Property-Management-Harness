# engine vs flat decomposition — normal

Seeds: 5 (1–5). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − flat): **-46,680**

## Night split

| outcome | nights | engine rev | flat rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 262.8 | 188,121 | 213,420 | -25,299 |
| neither_sold | 165.8 | 0 | 0 | 0 |
| only_engine_sold | 48.8 | 32,379 | 0 | 32,379 |
| only_flat_sold | 62.6 | 0 | 53,760 | -53,760 |

## By season

| season | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 35,869 | 47,400 | -11,531 | 0.568 | 0.479 | 478 | 750 |
| peak_ski | 159,450 | 177,660 | -18,210 | 0.528 | 0.615 | 940 | 900 |
| shoulder_spring | 25,181 | 42,120 | -16,939 | 0.770 | 0.745 | 376 | 650 |

## By property

| property | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 68,746 | 91,310 | -22,564 | 0.517 | 0.614 | 739 | 826 |
| overlook_ridge | 77,364 | 87,920 | -10,556 | 0.618 | 0.597 | 696 | 819 |
| summit_haus | 74,390 | 87,950 | -13,560 | 0.597 | 0.597 | 693 | 819 |

## By lead bucket

| lead_bucket | engine rev | flat rev | delta | engine nights | flat nights | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 20,195 | 17,980 | 2,215 | 31.200 | 22.800 | 647 | 789 |
| 121+ | 2,599 | 2,970 | -371 | 3.800 | 3.800 | 684 | 782 |
| 22-60 | 105,119 | 126,010 | -20,891 | 128.800 | 147.000 | 816 | 857 |
| 61-120 | 49,057 | 60,840 | -11,783 | 80.800 | 78.600 | 607 | 774 |
| 8-21 | 43,530 | 59,380 | -15,850 | 67.000 | 73.200 | 650 | 811 |
| unsold | 0 | 0 | 0 | 0.000 | 0.000 | 0 | 0 |

## Engine recommendations by season

| season | recs | at ceiling | at floor | guardrail actions |
|---|---:|---:|---:|---|
| early_winter | 8966 | 0.0% | 20.1% | clamped_decrease=18, clamped_increase=16, none=8087, sanity_floor=845 |
| peak_ski | 119702 | 32.8% | 0.0% | clamped_increase=89, none=109386, peak_blackout=10227 |
| shoulder_spring | 44220 | 0.0% | 23.2% | none=44220 |

## Engine guardrail on the day each night booked

| action | nights | revenue | at ceiling |
|---|---:|---:|---:|
| clamped_decrease | 0.2 | 74 | 0.0% |
| none | 280.6 | 195,260 | 26.4% |
| peak_blackout | 24.4 | 22,798 | 9.0% |
| sanity_floor | 6.4 | 2,368 | 0.0% |

## Scoreboard reconciliation

```
{
  "engine": {
    "scoreboard_mean": 220500.21,
    "database_mean": 220500.21,
    "difference": 0.0
  },
  "flat": {
    "scoreboard_mean": 267180.0,
    "database_mean": 267180.0,
    "difference": 0.0
  }
}
```
