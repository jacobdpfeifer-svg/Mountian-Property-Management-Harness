# Winter Park Resort Intelligence — daily operations

Resort lift/trail history is captured **only** when the signal cycle runs.
Skipped days are permanently lost (same discipline as `pacing_snapshots`).

## Daily command

```bash
wp-price signals cycle
```

Run once per day, ideally before `wp-price recommend`. On macOS, add to crontab:

```cron
0 6 * * * cd "/Users/jacobpfeifer/Harness for my wonderful Mother" && wp-price signals cycle >> data/logs/signals_cycle.log 2>&1
```

Create the log directory once: `mkdir -p data/logs`

## What the cycle captures

| Layer | Output |
|-------|--------|
| Intrawest feed | Per-lift/trail JSON → `resort_snapshots` |
| Derived signals | terrain %, lifts open, grooming %, resort open flag |
| Weather | wind gusts for wind-hold risk |
| SNOTEL | snowpack for terrain opening priors |
| CDOT | Berthoud access risk |
| Resort ops features | closure risk, surface forecast → `signal_features` |

## Briefs

```bash
wp-price signals resort-brief          # full Winter Park ops brief
wp-price signals brief                 # weekly summary includes ops snapshot
```

## One-time history backfill

```bash
python scripts/backfill_resort_history.py --from 2018-11-01
```

Runs weekly steps (SNOTEL + Open-Meteo per week). A full run from 2018 takes
**30–60+ minutes** because each SNOTEL pass ingests the full AWDB station history.
Use a narrow window to test first:

```bash
python scripts/backfill_resort_history.py --from 2025-12-01 --to 2025-12-08 --db data/backfill_test.db
```

Lift/trail daily history cannot be backfilled — only forward from first cycle.

## Reference data

- Machine-readable priors: `config/resort/winter_park.yaml`
- Monthly snowfall norms: `data/resort/winter_park_monthly_stats.csv`
- Curated events: `resort_events` table (seeded on `wp-price init-db`)

See also: `docs/PFEIFER_OPTIMIZATION_RUNBOOK.md`
