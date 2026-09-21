# Cloud 9 comp set runbook

Operational workflow for **Cloud 9 Chalet** (`cloud_9`, owner `cloud9`) live comp pricing.

All three Mont Luxe listings live in the default production DB (`data/wp_pricing.db`).
The isolated Cloud 9 database is retired; do not recreate it.

**Market:** `grand_home` — Winter Park / Fraser / Tabernash. Cloud 9 is physically in
Fraser; Guesty's mailing address is Winter Park. That is one market, not two.
**Operator-confirmed 2026-09-20: Cloud 9 stays in the shared `grand_home` market with
the twins — do not split it into a Fraser-only `market_id`.**

Owner-scoped reports:

```bash
wp-price report --from 2026-12-01 --to 2026-12-31 --owner cloud9
wp-price report --from 2026-12-01 --to 2026-12-31 --owner northwoods
```

`northwoods` is Summit Haus + Overlook Ridge. `cloud9` is Cloud 9 only.

## Data layout

| Path | Purpose |
|------|---------|
| [`data/cloud9/comps.csv`](../data/cloud9/comps.csv) | Comp catalog (`for_properties=cloud_9`). Airbnb members are discovered by the live sweep and kept/dropped using the brief rubric. |
| [`data/cloud9/comps_manual_snapshots.csv`](../data/cloud9/comps_manual_snapshots.csv) | Direct-book price rows (WPH, WPLC) — not in the Airbnb sweep |
| [`data/cloud9/properties.csv`](../data/cloud9/properties.csv) | Property bounds (floor $400, base ceiling $1,100, max $2,000) |
| [`data/cloud9/VALIDATION_MATRIX.md`](../data/cloud9/VALIDATION_MATRIX.md) | Scoring decisions and refresh notes (keep as the judgment log) |

Dec 2023 backtest data in [`data/dec2023/`](../data/dec2023/) remains separate — do not copy rates from it.

## Comp set (scraper-driven + human-reviewed)

Airbnb members refresh on the **same daily `wp-price scrape-comps` job** as the twins
(`scripts/daily_scrape.sh`, launchd `com.wpprice.scrape` at 07:00). The sweep is
market-wide; `comp_set_members` is the filter. Direct-book comps stay weekly-manual.

| Tier | comp_id | Name | Platform | Refresh |
|------|---------|------|----------|---------|
| Core | `comp_ranch_creek` | Ranch Creek Log Home | Airbnb | daily `scrape-comps` |
| Core | `comp_family_friendly` | Family Friendly 6BR | Airbnb | daily `scrape-comps` |
| Core | `comp_the_views` | The Views 6BR Chalet | Airbnb | daily `scrape-comps` |
| Core | `comp_lakota_reserve` | Lakota Reserve | WPLC direct | Manual snapshots |
| Value floor | `comp_deer` | Deer | WPH direct | Manual snapshots |
| Premium anchor | `comp_brooky` | Brooky | WPH direct | Manual snapshots |
| Premium SISO | `comp_wp_ski_house` | Winter Park Ski House | Airbnb | daily `scrape-comps` |

Inactive (kept for history): `comp_grand_park_retreat` — 2026-09-20 live payload is a 4BR Fraser townhouse.

**Hard excludes:** Summit Haus, Overlook Ridge (portfolio siblings). Granby / Grand Lake. Extra SISO when Ski House is already the premium ski-in/ski-out anchor.

## Daily / weekly commands

```bash
cd "Harness for my wonderful Mother"
source .venv/bin/activate

# Guesty inventory (system of record) — all 3 listings
wp-price sync-guesty

# Airbnb comp refresh for Cloud 9 AND the twins (Tue/Fri sampled windows)
# Scheduled: launchd com.wpprice.scrape (07:00). Manual:
wp-price scrape-comps --start 2026-11-25 --horizon 120

# After updating manual snapshot CSV (weekly during ski season)
# Comps-only: do not re-ingest properties.csv against a live Guesty DB
# (that would overwrite calibrated floors/ceilings).
wp-price ingest-csv --comps data/cloud9/comps_manual_snapshots.csv

# Pacing + health
wp-price snapshot
wp-price health

# Recommendations (Cloud 9 only)
wp-price recommend \
  --property cloud_9 --from 2026-12-01 --to 2026-12-31 --limit 500
# or: wp-price recommend --owner cloud9 --from 2026-12-01 --to 2026-12-31 --limit 500
```

## Fresh start

```bash
wp-price init-db
wp-price ingest-csv \
  --properties data/cloud9/properties.csv \
  --inventory data/cloud9/inventory.csv \
  --comps data/cloud9/comps.csv
wp-price ingest-csv \
  --properties data/cloud9/properties.csv \
  --inventory data/cloud9/inventory.csv \
  --comps data/cloud9/comps_manual_snapshots.csv
wp-price sync-guesty
wp-price scrape-comps --start 2026-11-25 --horizon 40
wp-price snapshot --backfill 14
wp-price health
```

`init-db` / `sync-guesty` against the default DB also contain Summit Haus and Overlook Ridge. Cloud 9 comps stay scoped via `for_properties=cloud_9`.

## Discovery (scraper first, then the rubric)

Re-rank the live market, then keep/drop using [`docs/CLOUD9_COMP_BRIEF.md`](CLOUD9_COMP_BRIEF.md) (score ≥70, substitutable). Do not paste the raw top-N into `comps.csv`.

```bash
# Cloud 9 hard filter: bedrooms ≥ 5, sleeps ≥ 16 when the payload has occupancy
wp-price discover-comps --date 2026-12-18 --min-price 800 --min-bedrooms 5 --min-sleeps 16 --limit 40
wp-price discover-comps --date 2026-12-05 --min-price 650 --min-bedrooms 5 --min-sleeps 16 --limit 40
wp-price discover-comps --date 2026-02-15 --min-price 700 --min-bedrooms 5 --min-sleeps 16 --limit 40
```

Unknown sleeps still appear when bedrooms pass (Airbnb often omits occupancy). Review those against the brief. Log the call in [`data/cloud9/VALIDATION_MATRIX.md`](../data/cloud9/VALIDATION_MATRIX.md). Then:

```bash
wp-price ingest-csv --comps data/cloud9/comps.csv
```

## Success gates

| Gate | Target |
|------|--------|
| Comp coverage | ≥ 60% |
| Comp freshness | < 48h (Airbnb via daily scrape; direct via weekly CSV) |
| Comp set size | ≥ 3 members (7 configured: 4 Airbnb + 3 direct) |
| Recommendations | Show `Comp set p75` in reason codes |

## Refresh cadence

- **Airbnb comps:** daily `scrape-comps` (`scripts/daily_scrape.sh` / `com.wpprice.scrape`) — same job as the twins
- **Discovery / set membership:** re-run `discover-comps` when a listing dies or a new Fraser/WP 16+ home appears; apply the brief; ingest
- **Direct comps (Deer, Brooky, Lakota Reserve):** weekly update of `comps_manual_snapshots.csv` from WPH/WPLC booking pages; re-ingest after editing

Update `as_of` column to today's date on each manual refresh so freshness gates pass.
