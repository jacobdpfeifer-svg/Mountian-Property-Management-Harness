# Comp data acquisition

Operator chose **scraper-first**, with a paid feed (AirDNA / Key Data) as the hybrid
fallback if the scraper proves weak. See `docs/LOCKED_INPUTS.md`.

## Why a market sweep, not per-comp requests

The obvious design — request each comp's price for each night — costs
`comps x nights` requests, which at a 120-day horizon is thousands of requests per
day and gets the source blocked almost immediately.

Airbnb's search endpoint returns **every bookable listing in a bounding box with a
parseable nightly rate in a single response** (measured: 280 Winter Park listings,
100% price-parse rate). So the scraper sweeps the market per date-window and filters
to the comp set afterwards. This is roughly two orders of magnitude fewer requests,
and it yields the whole-market distribution (`market_snapshots`) for free — which is
what makes "invisible in comps" detectable at all.

**Group-size tier.** Discovery and curated evidence filter to large-group peers
(`scrape.group_size`: default bedrooms ≥ 5, sleeps ≥ 14) so small units do not
contaminate ceilings for sleeps-16–18 homes. Market percentiles prefer sized
listings that pass the same filter when enough observations exist. Thresholds are
**owner-tunable** (twins are 5bd — a 6+ bedroom cutoff would be too strict).

**Sampling.** Windows are sampled one midweek (Tue) + one weekend (Fri) per week
rather than every night, because the ceiling consumes comp evidence at the
season x day-of-week level. `src/comps` falls back to nearby same-weekday-class
nights when a night has no exact observation, and labels the evidence accordingly.

## The failure mode this is built around

A scraper that throws is a nuisance. A scraper that **quietly returns plausible
garbage** is dangerous, because the number flows into the ceiling and then into an
auto-pushed rate. A markup change typically produces a constant, a stay-total
mistaken for a nightly rate, or three listings instead of 280 — none of which raise.

Defences, in order:

1. **Parse discipline** — the breakdown string states its own night count and is
   preferred over dividing a stay total by an assumed window length.
2. **Sweep validation** (`validate_sweep`) — rejects a window with too few listings,
   too low a parse rate, too many identical prices, or zero variance. A rejected
   sweep is discarded *entirely*; it is never partially trusted.
3. **Observation validation** (`validate_observation`) — rejects a comp price outside
   the plausible band or more than `max_change_ratio` from its last known value.
4. **Explicit status** — `comp_snapshots.scrape_status` separates `ok` /
   `unavailable` / `failed` / `blocked`. Only `ok` counts as evidence. Writing
   nothing on failure would make an outage indistinguishable from a fully-booked
   market, which is precisely the silent degradation the guardrails exist to catch.
5. **Run audit** — `comp_scrape_runs` records every run's window success rate, comp
   match rate, rejections and errors, with a verdict of `ok` / `degraded` / `failed`.
6. **Autonomy demotion** — degraded comp coverage or staleness demotes the engine to
   advisory via `src/guardrails`. There is a test asserting exactly this
   (`test_failed_scrape_demotes_autonomy`).

## Politeness

Default 4–8s randomised delay between requests. This is not only courtesy: an
aggressive sweep gets the IP blocked and the entire comp layer degrades to advisory.
Residential proxies are supported via `--proxy` / `scrape.proxy_url` and are
effectively required if the horizon or frequency is increased much.

Scraping public listing prices for competitive rate-setting is standard practice in
this industry (it is what AirDNA and PriceLabs do) but is contrary to Airbnb's terms
of service. That is the operator's commercial call. The provider interface exists so
switching to a licensed feed is a config change, not a rewrite.

## Usage

```bash
# Curate a comp set from the live market
wp-price discover-comps --date 2026-12-18 --min-price 400

# Refresh comp + market prices (daily)
wp-price scrape-comps --horizon 120

# Confirm what it bought you
wp-price health
```

Exit code is non-zero when the run is `degraded` or `failed`, so a cron wrapper can
alert without parsing output.
