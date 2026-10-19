# engine vs property_flat decomposition — normal

Seeds: 5 (1–5). All figures are per-seed means from retained job databases (simulated, not realized, revenue).

Total revenue delta (engine − property_flat): **38,105**

Ceiling/floor tolerance: 1% of the bound. "Model ≥ ceiling" is the share of recommendations whose model price was already at or above the ceiling, i.e. the ceiling, not the demand model, set the price.

## Night split

| outcome | nights | engine rev | property_flat rev | delta |
|---|---:|---:|---:|---:|
| both_sold | 358.8 | 316,209 | 277,048 | 39,161 |
| neither_sold | 125.4 | 0 | 0 | 0 |
| only_engine_sold | 24.2 | 24,608 | 0 | 24,608 |
| only_property_flat_sold | 31.6 | 0 | 25,665 | -25,665 |

## By season

| season | engine rev | property_flat rev | delta | engine occ | property_flat occ | engine ADR | property_flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 36,865 | 31,736 | 5,129 | 0.538 | 0.539 | 519 | 446 |
| peak_ski | 278,913 | 249,120 | 29,793 | 0.764 | 0.783 | 1,137 | 992 |
| shoulder_spring | 25,040 | 21,857 | 3,183 | 0.765 | 0.782 | 376 | 321 |

## By property

| property | engine rev | property_flat rev | delta | engine occ | property_flat occ | engine ADR | property_flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 111,168 | 107,374 | 3,794 | 0.722 | 0.738 | 855 | 809 |
| overlook_ridge | 94,570 | 106,159 | -11,589 | 0.696 | 0.713 | 755 | 827 |
| summit_haus | 135,080 | 89,180 | 45,900 | 0.710 | 0.718 | 1,057 | 690 |

## By lead bucket

| lead_bucket | engine rev | property_flat rev | delta | engine nights | property_flat nights | engine ADR | property_flat ADR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-7 | 16,809 | 15,271 | 1,538 | 25.800 | 26.400 | 652 | 578 |
| 121+ | 987 | 1,173 | -186 | 2.600 | 3.200 | 380 | 367 |
| 22-60 | 156,331 | 133,838 | 22,493 | 158.200 | 153.400 | 988 | 872 |
| 61-120 | 108,828 | 96,707 | 12,121 | 116.600 | 123.600 | 933 | 782 |
| 8-21 | 57,863 | 55,723 | 2,140 | 79.800 | 83.800 | 725 | 665 |
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
  "property_flat": {
    "scoreboard_mean": 302712.94,
    "database_mean": 302712.94,
    "difference": -0.0
  }
}
```
