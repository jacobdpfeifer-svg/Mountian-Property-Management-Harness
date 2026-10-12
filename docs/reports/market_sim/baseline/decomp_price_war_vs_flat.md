# engine vs flat decomposition — price_war

Seeds: 30 (1–30). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − flat): **-91,144**

## Night split

| outcome | nights | engine rev | flat rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 202.4 | 135,351 | 159,465 | -24,114 |
| neither_sold | 173.3 | 0 | 0 | 0 |
| only_engine_sold | 50.5 | 32,968 | 0 | 32,968 |
| only_flat_sold | 113.8 | 0 | 99,998 | -99,998 |

## By season

| season | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 33,116 | 44,100 | -10,984 | 0.537 | 0.446 | 468 | 750 |
| peak_ski | 109,237 | 173,070 | -63,833 | 0.351 | 0.599 | 968 | 900 |
| shoulder_spring | 25,967 | 42,293 | -16,326 | 0.797 | 0.748 | 375 | 650 |

## By property

| property | engine rev | flat rev | delta | engine occ | flat occ | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 34,411 | 87,125 | -52,714 | 0.321 | 0.590 | 596 | 820 |
| overlook_ridge | 53,883 | 85,328 | -31,446 | 0.447 | 0.578 | 669 | 820 |
| summit_haus | 80,025 | 87,010 | -6,985 | 0.637 | 0.588 | 697 | 822 |

## By lead bucket

| lead_bucket | engine rev | flat rev | delta | engine nights | flat nights | engine ADR | flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 13,104 | 16,785 | -3,681 | 22.500 | 21.100 | 582 | 796 |
| 121+ | 586 | 810 | -224 | 1.470 | 1.230 | 400 | 657 |
| 22-60 | 74,328 | 118,053 | -43,725 | 97.900 | 138.470 | 759 | 853 |
| 61-120 | 38,590 | 61,410 | -22,820 | 64.400 | 78.900 | 599 | 778 |
| 8-21 | 41,710 | 62,405 | -20,695 | 66.670 | 76.470 | 626 | 816 |
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
  "flat": {
    "scoreboard_mean": 259463.33,
    "database_mean": 259463.33,
    "difference": 0.0
  }
}
```
