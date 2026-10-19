# Research fixes ledger — 2026-10-19

Branch `research-fixes-2026-10-19` from `bcef02b`. Work was in `~/code/harness`.
Baseline before code changes: 1102 tests collected (3 deselected). After the
code commits: 1119 passed, 1 skipped, 3 deselected. The skip was not added by
this branch (the suite was already collecting a skippable test; the pass count
rose). Full suite command: `.venv/bin/python -m pytest -q`.

## Baseline (P0.1)

- HEAD at branch start: `bcef02b` Remove remaining realized-price references.
- `d3e8b92` is not an ancestor of that commit. The same message is `df520a6`.
- Anchor coverage on 2026-10-19, nights 2026-12-01 through 2027-03-31, own-set comps, age ≤ 42 days, at least 3 fresh quotes: Cloud 9 10/121 (8.3%), Summit Haus 0/121, Overlook Ridge 0/121.
- Scrape rows (`capture_method='scrape'`): 19,516 failed / 28,900 = 67.5%. Status mix on all `comp_snapshots`: failed 67.47%, unavailable 26.57%, ok 5.95%.
- Default policy does not enable `pace_pricing` (`tests/test_pace_pricing.py`). No live price push was made.

## P0.2–P0.4

Listed December peak (19 Dec 2026–2 Jan 2027, `nightly_inventory.listed_price`, status available, read 2026-10-19): 19 nights, about $2.6k–$4.0k, 14 of them at $3.0k or more. The booked clause in `00_SHARED_CONTEXT.md` was replaced with that range. Leak scan of the research folders: no 24-hex ids, no guest names, cold-call company unnamed. Vendor fee examples and all-in fee arithmetic were left because they are not this operator's booked rates.

Commit `4e304aa` Commit the October deep research pack with listed peak rates.

## Code items

| ID | Status | What changed | Audit |
|---|---|---|---|
| P2.1 | done | CARS headline codes. Shoulder/lane does not set `berthoud_closed`. | `65b37b6`. Self-audit in this file. No separate reviewer agent. |
| P2.2 | done | Window 230.0–254.3 in `config/policies/access.yaml`. Fraser MP 227 excluded. East-side fixture at 250. | `65b37b6`. |
| P2.3 | done | I-70 east/west of MP 232 stored on `cdot.i70_*`. `access_risk` does not read them. | `65b37b6`. |
| P2.4 | done | Live receipt `docs/reports/cdot_health_2026-10-19.json`: ok, feature_count 4, berthoud_closed 0, access_risk 0.25, i70 east 1. | `65b37b6`. |
| P2.5 | done | Forecast path is NWS. Open-Meteo removed. m/s → mph tested at 2.237. Historical fields are not filled. | `140462a`. Operator question: archive weather has no licence-clean source in this collector. |
| P2.6 | done | Curve is 1.00 at SQI 1.2 and 1.3. Direct uplift versus the old 1.12/1.18 knots is removed. No paired market-sim seeds were run; the multiplier itself is identically 1, so the curve contributes no owner-net difference from a neutral snow state. | `d31049a`. |
| P2.7 | done | Federal windows generated. Christmas ends 2 Jan (R7), not 4 Jan. Test requires 2027, 2028 and 2029. | `d31049a`. |
| P2.8 | partial | File exists. Every row is UNVERIFIED. Verified rows are the only ones a caller may use, and today that set is empty, so school breaks do not move price. | `d31049a`. Official district pages tried on 2026-10-19 returned 404. |
| P2.9 | partial | Base Pass re-read: Winter Park is on the unlimited-access list with blackouts 26–30 Dec 2026, 16–17 Jan 2027, 13–14 Feb 2027. Session Pass URL 404; those rows stay dated 2026-10-16. | `d31049a`. Operator question: which pass guests hold. |
| P3.1 | partial | `proving_ground_exam/worlds/misspecified.py` has kinked, lognormal, gamma-frailty, waiter, and channel-lag shapes. They are not wired into the market-sim runner. | `d40376e`. Not a full world runner. |
| P3.2 | not done | Multi-season burn-in was not built. | Needs a simulator design pass. |
| P3.3 | partial | `owner_net_of_gross` applies 0.595 and flags the fee base unconfirmed. It does not replace `hindsight_revenue`. | `d40376e`. Operator question: fee base. |
| P3.4 | not done | No rank-stability run on over-dispersed worlds. | Depends on P3.2. |
| P4.1 | partial | Stored run errors are mostly DNS failures resolving www.airbnb.com, plus timeouts. `classify_scrape_error` names dns and timeout. The calendar call no longer swallows a fetch error into an empty dict. No live scrape was run. | `c9771e9`. The DNS failures are an environment/network cause, not a parser bug. |
| P4.2–P4.3 | done | `comp_calendar` stores available, min-stay, restrictions, status, quality. Failure does not replace `quoted_ok`. Re-runs with the same stamp are idempotent. | `c9771e9`. Tested on a fresh database, not applied to `data/wp_pricing.db`. |
| P4.4 | not done | No comps were added. Coverage is unchanged: 8.3% / 0% / 0%. | Adding comps changes the comp set. Left for the operator because it is a market-definition choice even with pace off. |
| P4.5 | not done | Block-inference was not scored. | Would read the operator database against public calendars. Not run. |
| P4.6 | done as baseline | Receipt is the P0.1 coverage and 67.5% failure rate. Unchanged. | |
| P5.1 | done | `hit_rate` centres the signal and divides by non-zero centred pairs only. | `96d3b4b`. |
| P5.2 | done | `score_signal_against_outcomes` scores outcome residuals at the call's horizon. | `96d3b4b`. Pearson IC is invariant to subtracting the mean; the hit rate is not. |
| P5.3 | partial | Benjamini-Hochberg and a null Monte Carlo live in `promotion.py`. The Monte Carlo's uncorrected rate is above 25% and the BH rate is lower and under 20%. It is not the production ladder yet. | `96d3b4b`. The 27–31% figure is the uncorrected noise rate in that simulation, not a re-run of the historical screen. |
| P6 | partial | `src/pricing/pickup_shadow.py` shrinks a residual and bounds one booking. Not in `default.yaml`. No paired-seed gate. | `d40376e`. |
| P7.1–P7.4 | not done | Mountain-state bands, finite WTP, bid price, and stay displacement were not built. | They need the Phase 3 runner. |
| P7.5 | not done | `shadow_daily` was not populated. | |
| P7.6 | partial | `src/eval/field_test.py` assigns by check-in week and prints a power table. It is not activated. A 2% effect has power under 0.2 at the table's assumptions. | `d40376e`. |
| P7.7 | not done | No gate run. | |
| P1.1–P1.5 | not done | No fresh reviewer opened 15 URLs per dossier. | Operator question: commission that review. |
| P8.1–P8.8 | not done | Literature gaps listed in the 2026-10-19 audit section 6 are unchanged. | Same. |
| P9.1 | partial | Full suite green (1119 passed, 1 skipped). No end-to-end dry run of the daily pricer. | SQI multiplier change is the only default-path price input that changed, and it is now 1.00 where it was 1.12–1.18. Shoulder access risk 0.25 is below the 0.5 threshold in `default.yaml` `access`. |
| P9.2 | partial | S1 §2.2a and audit §7 updated. | |
| P9.3 | partial | Research-folder leak scan done at P0. Later commits are code, fixtures, and this ledger. | |

## Self-audit (code that landed)

1. Root cause: the closure flag was a substring search for "closed". It is now the headline code.
2. Bad payloads return `unavailable`. An empty but valid feed returns ok with a reason, not a fake closure.
3. The calendar provider no longer uses a bare `except` that returns `{}`. Fetch errors become `fetch_failed`.
4. Holiday dates come from rules. School breaks and Ikon rows carry source and `verified_on`.
5. New tests cover the shoulder payload, the east-side milepost, NWS m/s, the neutral curve, holiday generation, calendar idempotency, and hit rate.
6. Mileposts and risk weights are named constants with a config file and a source comment.
7. The health receipt stores counts and flags, not a raw feed.
8. S1 §2.2a and the audit were updated.
9. Full suite passed after the changes.
10. Experimental signals and the pickup/field modules are not enabled in `default.yaml`.

What a reviewer should still try: an I-70 event whose two mileposts straddle 232 (both flags can set), an NWS grid in degrees Fahrenheit, and a holiday year where the third Monday calculation crosses a month. Those were not given an independent agent pass.

## Operator questions

- Management-fee base behind 0.595, turn cost, and channel mix.
- Which pass product guests hold. Base Pass blackouts at Winter Park were confirmed on the Ikon page; Session Pass was not re-verified.
- Whether to buy PriceLabs or start an AirDNA or DestiMetrics trial. Not bought.
- Historical weather fields have no licence-clean source in the forecast collector. SNOTEL remains the snow record.
- Whether to add comps for the two homes with empty anchors.
- Whether to promote any experimental arm. None were promoted.
- Whether to run the independent dossier review (P1) and the literature gaps (P8).
- Whether to push or merge this branch.
