# Locked inputs (v1)

**Confirmed by the operator on 2026-08-27.** These supersede the plan defaults that the
first build assumed. Any module contradicting this table is a bug.

| Decision | Value | Consequence |
|---|---|---|
| System of record | **Guesty** (Open API, LIVE) | Connected and syncing 2026-08-29. `wp-price sync-guesty` pulls listings, calendar and reservations. Credentials in gitignored `.env`. CSV/iCal remain demo-only. |
| Comp data | **Scraper-first**, hybrid AirDNA/Key Data fallback if the scraper proves weak | Built: `src/scrape` market sweep via pyairbnb. Comp features remain an *unreliable dependency* — every number carries freshness + coverage, validated hard, and a degraded run demotes autonomy. See `docs/rules/COMP_DATA.md`. |
| History available | **6–12 months** | One ski season, no YoY. Season-scoped history is thin by construction — the ceiling MUST NOT silently fall back to whole-history statistics. See `docs/rules/PRICING_DOCTRINE.md` §Ceiling. |
| Authority | **Auto-push within guardrails** | Guardrails and the data-health gate are load-bearing safety code, not decoration. Nothing pushes without passing `src/guardrails`. |
| Objective | **RevPAN** | Price is chosen by maximizing `P × P(book|P)`, not by applying multipliers and hoping. |

## The risk this combination creates

Scraper-first **and** auto-push is the one genuinely dangerous pairing above. Bad scrapers
rarely crash; they quietly return partial or stale data. A depressed comp reading feeding an
auto-push loop can move real rates on real inventory before a human looks at a dashboard.

Mitigation, implemented in `src/guardrails/`: **autonomy is a computed function of data
health, not a configured setting.** See `docs/rules/AUTONOMY.md`.

## Live portfolio (from Guesty, 2026-08-29)

| Property | Guesty listing id | Address | Config |
|---|---|---|---|
| Summit Haus | `69f3fce1fd7011001188056e` | 312 N Woods Pl, Winter Park | 5bd / 5.5ba / sleeps 16 |
| Overlook Ridge | `69f14a198a424c00146db9d8` | 300 N Woods Pl, Winter Park | 5bd / 5.5ba / sleeps 16 |
| Cloud 9 | `6a8e355230f5b5007c81df4b` | 1615 Pioneer Trail, Winter Park | 6bd / 4ba / sleeps 18 |

Three active listings, not four. Summit Haus and Overlook Ridge are next-door twins on
N Woods Pl and are priced in lockstep.

**Guesty `basePrice` is NOT a ceiling.** It is a starting rate ($420/$618 on the twins)
that dynamic pricing adjusts upward; their calendar carries $2,600-2,841 at Christmas.
Property bounds are therefore recalibrated from observed listed + realised prices by
`sync.recalibrate_bounds`, never from `basePrice`.

## Still open

- **Write path unexercised.** `GuestyClient.set_rate` is implemented against
  `PUT /v1/availability-pricing/api/calendar/listings/{id}` but has never been fired at
  the live tenant — that changes real rates on real inventory and needs explicit
  authorisation. `--adapter dry_run` exercises everything up to the write.
- **Fourth property.** The operator described four; Guesty returns three active and
  zero inactive.
- **Whether Guesty exposes inquiry / quote-shown data.** Not found on the reservations
  endpoint; `booking_inquiries` stays empty and pacing velocity is the substitute.
- **Cloud 9 comp set curated (2026-09-01).** Eight comps in
  [`data/cloud9/comps.csv`](../data/cloud9/comps.csv) (5 Airbnb + 3 direct). Validated at
  100% coverage. Lives in the default production DB (`data/wp_pricing.db`) with the
  twins. Filter with `--owner cloud9` (Cloud 9) or `--owner northwoods` (Summit Haus
  + Overlook Ridge). See [`docs/CLOUD9_RUNBOOK.md`](CLOUD9_RUNBOOK.md).
- **Twins comp set still pipeline-exercise.** `data/scrape/comps.csv` serves
  `summit_haus|overlook_ridge`; `data/sample/comps.csv` is demo-only.
- **Comp scraper not run for twins.** Summit/Overlook comp coverage may still be 0% on
  the default DB until `scrape-comps` is run against their comp set.
- **Proxy.** Direct sweeps work today. If horizon or frequency increases materially,
  residential proxies become necessary (`--proxy`).
