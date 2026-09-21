# Cloud 9 Chalet — Comp Discovery Brief

Purpose: Find 5–10 ideal comparable vacation rentals for Cloud 9 Chalet.
Comps feed a RevPAN pricing engine that uses the **75th percentile** of comp listed nightly
rates (when fresh and ≥60% coverage) to inform rate ceilings. Quality matters more than quantity.

**How the set is produced:** `wp-price discover-comps` sweeps the `grand_home` bbox
(Winter Park / Fraser / Tabernash). A human then applies this rubric (accept ≥70) and
writes keepers to `data/cloud9/comps.csv`. Nightly rates refresh automatically via the
same `wp-price scrape-comps` job as Summit Haus and Overlook Ridge. This brief is the
filter, not a one-time hand-built catalog.

## Subject Property Profile

| Field | Value |
|-------|-------|
| Property ID | `cloud_9` |
| Name | Cloud 9 Chalet |
| Address | 1615 Pioneer Trail, Winter Park, CO 80482 (Guesty mailing city) |
| Town (operator-confirmed) | Fraser, CO — adjacent to Winter Park; same `grand_home` market |
| Guesty listing ID | `6a8e355230f5b5007c81df4b` |
| Bedrooms / baths | 6 bed / 4–4.5 ba |
| Sleeps | 18 |
| Luxury tier | luxury |
| Target ALOS | 4 nights (large groups, ski-week stays) |
| Timezone | America/Denver |
| Configured rate bounds | Floor $400 · Base ceiling $1,100 · Max ceiling $2,000 |
| Amenities (known) | Hot tub · Mountain view · Fireplace · Game room · Nordic trails access |
| NOT known to be | Ski-in/ski-out · Elevator · Dual kitchen · Downtown walkable |

**Product positioning:** Cloud 9 is a large-group luxury whole-home chalet — the buyer persona
is multi-family ski trips, corporate retreats, and friend groups needing 16–18+ beds, not couples
or small families. It competes in the upper-mid to ultra-luxury large-home segment of the
Winter Park / Fraser STR market, not the 3–4BR cabin tier.

## Geographic Market Definition

**Primary market (must be in this area):** Winter Park / Fraser / Tabernash, Grand County, CO
(`market_id: grand_home` in `config/policies/markets.yaml`). Fraser is scored 85/100 on
proximity vs Pioneer/Lakota/Grand Park at 100 — comps may span both towns on purpose.

Bounding box (scraper): NE 39.95°N, -105.70°W · SW 39.85°N, -105.82°W (~280 bookable Airbnb listings)

**Do NOT use as primary comps:** Breckenridge, Vail, Steamboat, Granby/Grand Lake.

## Ideal Comp Criteria (Must-Haves)

**Hard filters:**
- Sleeps ≥ 16 (ideal: 16–19; Cloud 9 sleeps 18)
- Whole-home luxury chalet/house — not condo, not hotel-style
- Geography: Winter Park, Fraser, or Tabernash
- Bedrooms ≥ 5
- Actively listed on Airbnb, Vrbo, or major PM direct site
- Observable nightly rates for ski season (Dec–Mar)
- Airbnb room ID available for automated scraping

**Strong preference:** Similar guest capacity (16–18), hot tub, professional PM, new/recent homes,
4–7 night min-stay during holidays, rate band overlap ($650–$1,750 peak).

**Exclusion criteria:** Summit Haus, Overlook Ridge (same portfolio), sleeps <14, 3–4BR cabins,
Brooky-tier ultra-mansions as sole comps, budget tier, inactive listings.

## Scoring Rubric (0–100, accept ≥70)

| Factor | Weight | Guidance |
|--------|--------|----------|
| Sleep capacity match (16–19) | 25% | 18 = 100, 16–17 = 85 |
| Luxury tier / finishes | 20% | Professional PM luxury = 100 |
| Geographic proximity | 15% | Pioneer/Lakota/Grand Park = 100; Fraser = 85 |
| Amenity parity | 15% | Hot tub, game room, views |
| Rate band overlap | 15% | Peak within ±25% of $1,100–$1,400 |
| Data availability | 10% | Scrapeable room ID = 100; direct-only = 50 |

## Required Output Format (CSV)

```csv
comp_id,name,bedrooms,bathrooms,amenities,notes,source_url,airbnb_room_id,platform,for_properties
```

Example:

```csv
comp_ranch_creek,Ranch Creek Log Home,5,4.0,hot tub|fireplace|mountain views,Sleeps 18; Fraser large-group luxury,https://www.airbnb.com/rooms/897819634480326640,897819634480326640,airbnb,cloud_9
```

Field rules: `comp_id` snake_case; `for_properties` must include `cloud_9`; pipe-separated amenities.

## How Comps Are Used

- Engine takes **p75** of comp listed nightly rates per stay date
- Comp evidence blends into ceiling at **30% weight** (`comp_blend_weight`) when fresh (<48h) and ≥60% coverage
- Comps must be substitutable — a guest choosing Cloud 9 would realistically consider these alternatives
- Include 1 ultra-luxury anchor (Brooky-tier) and 1 value floor (Deer/Rifle Shot-tier)
- Max 1–2 ski-in/ski-out premium anchors balanced with valley large homes

## Live Comp Set (scraper-reviewed 2026-09-20)

See [`data/cloud9/VALIDATION_MATRIX.md`](../data/cloud9/VALIDATION_MATRIX.md) for scoring
and the 2026-09-20 overlap vs rejects. Membership is not frozen: re-run discovery, apply
this rubric, ingest, and let `scrape-comps` refresh prices.

| Tier | comp_id | Name |
|------|---------|------|
| Core | comp_ranch_creek | Ranch Creek Log Home |
| Core | comp_family_friendly | Family Friendly 6BR |
| Core | comp_the_views | The Views 6BR Chalet |
| Core | comp_lakota_reserve | Lakota Reserve (direct) |
| Value floor | comp_deer | Deer (direct) |
| Premium anchor | comp_brooky | Brooky (direct) |
| Premium SISO | comp_wp_ski_house | Winter Park Ski House |

`comp_grand_park_retreat` is inactive (live 4BR townhouse).

## Discovery Commands

```bash
wp-price discover-comps --date 2026-12-18 --min-price 800 --min-bedrooms 5 --min-sleeps 16
wp-price discover-comps --date 2026-12-05 --min-price 650 --min-bedrooms 5 --min-sleeps 16
wp-price discover-comps --date 2026-02-15 --min-price 700 --min-bedrooms 5 --min-sleeps 16
```

`--min-sleeps 16` is Cloud 9’s hard filter. The twins default (`scrape.group_size.min_sleeps: 14`)
is too loose for this listing. Listings with unknown sleeps but bedrooms ≥ 5 still print for
review — keep only if a guest choosing Cloud 9 would realistically book them.

## Dec 2023 Candidate Pool

The seven comps in [`data/dec2023/comps.csv`](../data/dec2023/comps.csv) are a **candidate pool
only** — identities may be included if re-validated with live 2025–26 research; 2023 rate
snapshots are never copied. Overlook Ridge is always excluded (portfolio sibling).

## Operational Reference

See [`docs/CLOUD9_RUNBOOK.md`](CLOUD9_RUNBOOK.md) for ingest, scrape, and refresh workflow.
