# Cloud 9 comp set runbook

Operational workflow for **Cloud 9 Chalet** (`cloud_9`) live comp pricing.

## Data layout

| Path | Purpose |
|------|---------|
| [`data/cloud9/comps.csv`](../data/cloud9/comps.csv) | Comp catalog (8 comps, `for_properties=cloud_9`) |
| [`data/cloud9/comps_manual_snapshots.csv`](../data/cloud9/comps_manual_snapshots.csv) | Direct-book price rows (WPH, WPLC) |
| [`data/cloud9/properties.csv`](../data/cloud9/properties.csv) | Property bounds (floor $400, base ceiling $1,100, max $2,000) |
| [`data/cloud9/VALIDATION_MATRIX.md`](../data/cloud9/VALIDATION_MATRIX.md) | Scoring decisions and rate sources |
| [`data/cloud9_run.db`](../data/cloud9_run.db) | Isolated DB for Cloud 9 comp + Guesty workflow |

Dec 2023 backtest data in [`data/dec2023/`](../data/dec2023/) remains separate — do not copy rates from it.

## Comp set (8 comps)

| Tier | comp_id | Name | Platform | Refresh |
|------|---------|------|----------|---------|
| Core | `comp_ranch_creek` | Ranch Creek Log Home | Airbnb | `scrape-comps` |
| Core | `comp_family_friendly` | Family Friendly 6BR | Airbnb | `scrape-comps` |
| Core | `comp_the_views` | The Views 6BR Chalet | Airbnb | `scrape-comps` |
| Core | `comp_grand_park_retreat` | Luxury Grand Park Retreat | Airbnb | `scrape-comps` |
| Core | `comp_lakota_reserve` | Lakota Reserve | WPLC direct | Manual snapshots |
| Value floor | `comp_deer` | Deer | WPH direct | Manual snapshots |
| Premium anchor | `comp_brooky` | Brooky | WPH direct | Manual snapshots |
| Premium SISO | `comp_wp_ski_house` | Winter Park Ski House | Airbnb | `scrape-comps` |

**Hard excludes:** Summit Haus, Overlook Ridge (portfolio siblings).

## Daily / weekly commands

```bash
cd "Harness for my wonderful Mother"
source .venv/bin/activate

# Guesty inventory (system of record)
wp-price --db data/cloud9_run.db sync-guesty

# Airbnb comp refresh (Tue/Fri sampled windows)
wp-price --db data/cloud9_run.db scrape-comps --start 2026-11-25 --horizon 120

# After updating manual snapshot CSV (weekly during ski season)
wp-price --db data/cloud9_run.db ingest-csv \
  --properties data/cloud9/properties.csv \
  --inventory data/cloud9/inventory.csv \
  --comps data/cloud9/comps_manual_snapshots.csv

# Pacing + health
wp-price --db data/cloud9_run.db snapshot
wp-price --db data/cloud9_run.db health

# Recommendations
wp-price --db data/cloud9_run.db recommend \
  --property cloud_9 --from 2026-12-01 --to 2026-12-31 --limit 500
```

## Fresh start

```bash
wp-price --db data/cloud9_run.db init-db
wp-price --db data/cloud9_run.db ingest-csv \
  --properties data/cloud9/properties.csv \
  --inventory data/cloud9/inventory.csv \
  --comps data/cloud9/comps.csv
wp-price --db data/cloud9_run.db ingest-csv \
  --properties data/cloud9/properties.csv \
  --inventory data/cloud9/inventory.csv \
  --comps data/cloud9/comps_manual_snapshots.csv
wp-price --db data/cloud9_run.db sync-guesty
wp-price --db data/cloud9_run.db scrape-comps --start 2026-11-25 --horizon 40
wp-price --db data/cloud9_run.db snapshot --backfill 14
wp-price --db data/cloud9_run.db health
```

## Discovery (curate new comps)

```bash
wp-price discover-comps --date 2026-12-18 --min-price 800 --limit 40
wp-price discover-comps --date 2026-12-05 --min-price 700 --limit 40
wp-price discover-comps --date 2026-02-15 --min-price 700 --limit 40
```

Score candidates ≥70 per [`docs/CLOUD9_COMP_BRIEF.md`](CLOUD9_COMP_BRIEF.md). Add to `data/cloud9/comps.csv` with `for_properties=cloud_9`.

## Success gates

| Gate | Target |
|------|--------|
| Comp coverage | ≥ 60% (validated at 100% on 2026-09-01) |
| Comp freshness | < 48h |
| Comp set size | ≥ 3 members (8 configured) |
| Recommendations | Show `Comp set p75` in reason codes |

## Manual refresh cadence

- **Airbnb comps:** daily `scrape-comps` during ski season
- **Direct comps (Deer, Brooky, Lakota Reserve):** weekly update of `comps_manual_snapshots.csv` from WPH/WPLC booking pages; re-ingest after editing

Update `as_of` column to today's date on each manual refresh so freshness gates pass.
