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
- **Comp scraper has not been run against the real comp set.** Comp coverage is 0%, so
  autonomy is gated at `suggest`.
- **Comp set curation.** `data/sample/comps.csv` holds five real Winter Park room ids
  found via `discover-comps`, but they were picked to exercise the pipeline, not
  chosen as genuine luxury comparables. The operator should curate the real set.
- **Proxy.** Direct sweeps work today. If horizon or frequency increases materially,
  residential proxies become necessary (`--proxy`).
