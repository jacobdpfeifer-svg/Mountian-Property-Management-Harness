# Property diagnosis, corrected baseline (`normal`)

Source: retained databases in `~/wp-price-runs/market_sim/baseline_79dae5d`, 30 seeds, scenario `normal`. Simulated shopper revenue only. Choice-loss reasons are not in these databases; the next run records them in `sim_choice_trace`.

Peak occupancy is one minus the unsold share of peak nights.

| property | peak engine price | peak flat | peak comp | peak ceiling | peak final | peak unsold share | peak occupancy |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cloud 9 | 1,124 | 900 | 760 | 1,173 | 1,147 | 0.90 | about 10% |
| Overlook Ridge | 1,044 | 900 | 758 | 1,048 | 1,042 | 0.69 | about 31% |
| Summit Haus | 904 | 900 | 764 | 907 | 900 | 0.37 | about 63% |

Cloud 9 and Overlook are priced about $140–$220 above the flat peak rate and about $280–$360 above the comp median. Summit Haus matches the flat peak rate. Early winter and shoulder go the other way: the engine's final price sits near the floor and well below both the flat rate and the comps.

A ceiling probe on seed 1 as of 1 Nov 2026, before this season's own bookings, finds **zero booked sales and zero past listed nights** in the simulator database. The peak ceiling is the thin seasonal anchor, which is each home's base times the 1.15 peak multiplier: about 1,190 for Cloud 9 (base 1,035), 1,053 for Overlook (base 916), and 912 for Summit (base 793). The reporting band on that empty sample is about ±35%. A cap set at base × 1.15 would not move the price. The candidate caps therefore use the property base itself (1,035 and 916), which is still above the $900 flat benchmark.

Regenerate with:

```bash
PYTHONPATH=. .venv/bin/python scripts/property_diagnostics.py \
  ~/wp-price-runs/market_sim/baseline_79dae5d --scenario normal
```
