# Cloud 9 Comp Validation Matrix

**Validated:** 2026-09-01  
**Subject:** Cloud 9 Chalet (`cloud_9`) — 6BR / 18 sleep, Pioneer Trail valley  
**Method:** Dec 2023 identities re-scored against brief rubric + live discovery (`discover-comps` Dec 5/18 2026, Feb 15 2026) + WPH/WPLC/Vrbo listing verification

## Dec 2023 Candidate Pool

| comp_id | Name | Score | Tier | Decision | Rationale |
|---------|------|-------|------|----------|-----------|
| comp_lakota_reserve | Lakota Reserve | 90 | Core | **Include** | 18 sleep, 6/6.5BR, WPLC luxury, hot tub, game room, Lakota cluster; actively listed Sep 2026 |
| comp_rifle_shot | Rifle Shot | 82 | Core/value | **Exclude** | Valid substitute but direct-only; superseded by `comp_grand_park_retreat` (Airbnb Grand Park peer, scrapeable) |
| comp_deer | Deer | 86 | Value floor | **Include** | 16 sleep, 7/5.5BR, WPH shuttle route, hot tub, game room; rate band overlaps Cloud 9 shoulder |
| comp_brooky | Brooky | 76 | Premium anchor | **Include** | Ultra-luxury 8000 sqft ceiling anchor; 16+ sleep, hot tub, game room; still listed WPH Sep 2026 |
| comp_corridor_way | Corridor Way Chalet | 78 | SISO anchor | **Exclude** | Valid SISO premium but Vrbo-only; `comp_wp_ski_house` covers SISO tier with Airbnb scrape path |
| comp_moose | Moose | 72 | Core (downtown) | **Exclude** | 19 sleep passes capacity but downtown location (score 70 geo) is weaker valley substitute vs Pioneer Trail |
| comp_overlook_ridge | Overlook Ridge | — | — | **Exclude** | Portfolio sibling (same operator as Summit Haus); hard exclude per brief |

## Airbnb Discovery Additions

| comp_id | Name | Score | Tier | Decision | Discovery evidence |
|---------|------|-------|------|----------|-------------------|
| comp_ranch_creek | Ranch Creek Log Home | 92 | Core | **Include** | 18 sleep Fraser luxury; $1360 Dec 5 / $1331 Feb 15 / $2828 Dec 18 window |
| comp_family_friendly | Family Friendly 6BR | 84 | Core | **Include** | 16 sleep valley whole-home; $814 Dec 5 shoulder |
| comp_the_views | The Views 6BR Chalet | 85 | Core | **Include** | 16 sleep Fraser luxury; $728 Dec 5 shoulder |
| comp_wp_ski_house | Winter Park Ski House | 78 | Premium SISO | **Include** | 16 sleep ski-in/ski-out; $2004 Dec 5 / $1652 Feb 15 |
| comp_grand_park_retreat | Luxury Grand Park Retreat | 80 | Core | **Include** | Grand Park new-build cluster; $1425 Dec 18 peak; replaces Rifle Shot for scrape coverage |

## Final Live Set (8 comps on 2026-09-01; 7 after 2026-09-20 refresh)

| Tier | Count | Comps |
|------|-------|-------|
| Core | 4 (was 5) | Ranch Creek, Family Friendly, The Views, Lakota Reserve. Grand Park Retreat dropped (4BR townhouse). |
| Value floor | 1 | Deer |
| Premium anchor | 2 | Brooky (ultra-luxury, direct), Winter Park Ski House (SISO, Airbnb) |

See **2026-09-20 scraper refresh** below for the live-sweep overlap and rejects.

## 2026-09-20 scraper refresh

Live `wp-price discover-comps` against the same `grand_home` bbox (Winter Park / Fraser / Tabernash), with bedrooms parsed from Airbnb `structuredContent` and Cloud 9 hard filters (`bd≥5`, `sleeps≥16` when known).

| room_id | Name | Decision | Why |
|---------|------|----------|-----|
| 897819634480326640 | Ranch Creek Log Home | **Keep** | Overlap with manual set. Title `Home in Fraser`, 5BR. Substitutable Fraser large-group luxury. |
| 28918989 | Family Friendly 6BR | **Keep** | Overlap. Title `Home in Winter Park`, 6BR / sleeps 16 in name. |
| 22769369 | The Views 6BR | **Keep** | Overlap. Title `Home in Fraser`, 6BR / sleeps 16. Missed a `--min-price 700` pass at $696 that night — price floor is not a delist signal. |
| 998026465866480254 | Winter Park Ski House | **Keep** | Overlap. Sole SISO premium anchor. |
| 1761114119243255736 | Luxury Grand Park Retreat | **Drop (inactive)** | Live payload is **4BR townhouse in Fraser**. Fails bedrooms ≥ 5. Original “sleeps 18 est” does not hold. |
| 1408168171167279157 | Slopeside Luxury Chalet | **Reject** | Twins-tier SISO; sleeps 14 in twins notes; Cloud 9 already has one SISO. |
| 1473395104176598155 | Secluded Ranch Creek | **Reject** | Live 4BR Fraser; twins keep at sleeps 14. |
| 48424415 | Downtown WP Timber Top | **Reject** | Title `Home in Granby` — Granby is out of primary market. |
| 1134265223418214424 | WP Resort Villa 510 | **Reject** | Resort-villa product; sleeps unknown; would-a-guest-choose-Cloud-9 bar not met vs valley chalets. |
| 1044902831329968565 | Moose Lodge | **Reject** | Same downtown-Moose judgment as 2026-09-01 (geo weaker than Pioneer/Fraser valley). |
| 1767097517715247917 | Sleeps 18 / 2 hot tubs | **Reject** | Capacity match, but Christmas $2,957 is Brooky-tier ultra; Cloud 9 already has Brooky as the ceiling anchor. Adding it would pull p75. |

**Live set after refresh:** 4 Airbnb (scrape-comps) + 3 direct (weekly CSV) = 7. Direct comps are not in the Airbnb sweep by design.

## Rate Sources (2025–26)

| Comp | Shoulder (Dec 5) | Peak (Dec 18–26) | Feb (Presidents) | Source |
|------|------------------|------------------|------------------|--------|
| Ranch Creek | $1,360 | $2,828* | $1,331 | `discover-comps` live sweep |
| Family Friendly | $814 | — | — | `discover-comps` live sweep |
| The Views | $728 | — | — | `discover-comps` live sweep |
| WP Ski House | $2,004 | — | $1,652 | `discover-comps` live sweep |
| Grand Park Retreat | — | $1,425 | — | `discover-comps` live sweep |
| Lakota Reserve | $950 | $1,650 | $1,100 | WPLC listing + market band research Sep 2026 |
| Deer | $750 | $1,350 | $950 | WPH listing + market band research Sep 2026 |
| Brooky | $1,100 | $1,900 | $1,250 | WPH listing + market band research Sep 2026 |

*2-night window totals from sweep; scrape-comps normalizes to nightly rate.
