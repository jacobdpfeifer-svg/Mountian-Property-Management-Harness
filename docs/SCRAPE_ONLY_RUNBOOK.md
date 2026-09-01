# Scrape-only runbook (no Guesty)

Use this workflow when inventory and comps must come entirely from public Airbnb market
scrapes — no Guesty sync, no PMS API.

## Portfolio

- **Properties:** Summit Haus (`summit_haus`), Overlook Ridge (`overlook_ridge`)
- **Seed data:** [`data/scrape/`](../data/scrape/)
- **Note:** These twins are often **direct-book only** (not listed on Airbnb). When
  `discover-properties` cannot match by name, the engine assigns a **luxury 5BR+ market
  proxy** from the Winter Park sweep and applies the same price curve to both twins.

## Daily / on-demand commands

```bash
cd "Harness for my wonderful Mother"
source .venv/bin/activate

# One-time / fresh start
wp-price init-db
wp-price seed-scrape

# Resolve Airbnb room ids (persists to properties.airbnb_room_id)
wp-price discover-properties \
  --date 2026-12-18,2026-12-24,2026-12-05 \
  --min-price 400 --persist

# Subject inventory for a date range
wp-price scrape-properties --from 2026-12-01 --to 2026-12-31

# Comp + market prices (sampled Tue/Fri windows)
wp-price scrape-comps --start 2026-11-25 --horizon 40

# Signals (SNOTEL, calendars → demand_signals, ENSO, weather)
wp-price signals cycle --as-of 2026-09-01

# Pacing bootstrap (first run) + today's capture
wp-price snapshot --backfill 14
wp-price snapshot

# Recommend, export, audit
wp-price health
wp-price recommend --from 2026-12-01 --to 2026-12-31 \
  --property summit_haus,overlook_ridge --limit 500
wp-price export --from 2026-12-01 --to 2026-12-31 \
  --property summit_haus,overlook_ridge -o data/exports/dec2026_rates.csv
wp-price audit --from 2026-12-01 --to 2026-12-31 \
  --property summit_haus,overlook_ridge -o data/exports/dec2026_audit.md

# Exercise push path without writes
wp-price push --from 2026-12-01 --to 2026-12-31 \
  --property summit_haus,overlook_ridge --adapter dry_run
```

## Interpreting discovery

| Output | Meaning |
|--------|---------|
| `score >= 10` | Confident name/address match on Airbnb |
| `score == 1`, `PROXY:` prefix | Luxury market proxy — subject not on Airbnb |
| Same `room_id` on both twins | Expected — shared price curve for lockstep twins |

## Known limitations

1. **No booked_price history** without PMS — ceiling leans on listed anchors and comps.
2. **Proxy listed prices** can sit far below recalibrated seasonal anchors → `sanity_floor`
   guardrail raises recommendations and marks nights `blocked`.
3. **Pacing backfill** is reconstructed from current inventory (biased) until daily
   `wp-price snapshot` runs accumulate real history.
4. **Comp scrape** samples Tue/Fri windows — not every calendar night has a direct comp obs.

## Kill switches

- SQI misbehaving: `config/policies/conditions.yaml` → `sqi.enabled: false`
- Disable proxy fallback (discovery only): set `allow_proxy_fallback=False` in code or
  provide `airbnb_room_id` manually in [`data/scrape/properties.csv`](../data/scrape/properties.csv)

## Improvement backlog (prioritized)

| Priority | Item | Status |
|----------|------|--------|
| P0 | `wp-price scrape-properties` | Done |
| P0 | `properties.airbnb_room_id` + discovery | Done |
| P1 | `wp-price export` | Done |
| P1 | `wp-price audit` | Done |
| P1 | This runbook | Done |
| P2 | Direct-booking scraper (Elysian/VRBO) for true twin inventory | Open |
| P2 | Per-night `pyairbnb.price.get` fill when sweep sparse | Open |
| P2 | Twin lockstep constraint in compose | Open |
| P3 | Curate luxury comp set (replace pipeline test picks) | Open |
| P3 | Booked-price bootstrap without Guesty | Open |
