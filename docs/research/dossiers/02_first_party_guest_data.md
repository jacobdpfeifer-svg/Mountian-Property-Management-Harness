# Dossier 2 — Mont Luxe first-party guest data

Date: 2026-09-29
Access date for web sources: 2026-09-29

## Question

What can be collected from Guesty, Airbnb, VRBO, and the direct site without putting names, emails, or phones in the pricing database, and what can 3 homes actually teach?

## Guesty fields

Open API guest report parameters include `guestHometown` (town or city). Source: https://open-api-docs.guesty.com/docs/fields-for-guest-reports

Reservation stay objects include `numberOfGuests.numberOfAdults`, `numberOfChildren`, `numberOfInfants`, and `numberOfPets`. Source: https://open-api-docs.guesty.com/reference/reservationsopenapicontroller_getreservationsbyids

A create-reservation example also shows guest `hometown`, `nationality`, `email`, `phone`, and `fullName`. Source: https://open-api-docs.guesty.com/docs/create-a-reservation — those contact fields are **out of scope** for the pricing DB.

`GET /reservations/{id}` is documented as deprecated in favor of a newer endpoint. Localized check-in dates (`checkInDateLocalized`) follow the listing timezone. Source: https://open-api-docs.guesty.com/reference/get_reservations-id

**UNVERIFIED.** The exact rate-limit numbers on the current Guesty plan. The public docs reviewed here do not state a single numeric limit. Treat 429s as a sync backoff, not as a reason to store raw payloads.

Channel masking: Airbnb often withholds full guest contact until booking. Which hometown fields survive on `source=airbnb2` versus `website` is **unknown** until a dry-run sync prints field presence with values redacted. The data contract in Phase 4 records availability as "channel-dependent."

## Airbnb and VRBO host surfaces

**UNVERIFIED as a field list.** This pass did not reproduce Airbnb’s host-insight screens or VRBO’s demand dashboard. Both are host-login products. Their terms restrict scraping. Do not scrape guest messages or profiles. Use only what Guesty already receives as the system of record.

## Direct site

Ethical capture, if the operator adds it later: UTM source, device class, and a city from IP truncated to city/state, plus a consented email that **stays out of** `wp_pricing.db`. Consent is required before using that email for research (Colorado Privacy Act applies to personal data of Colorado residents; guests may also be in CCPA or GDPR scope if they are California or EU residents). CPA overview: https://coag.gov/resources/colorado-privacy-act/ (access 2026-09-29).

## What the current sync stores

`src/pms/sync.py` writes `status`, `source`, `confirmed_at`, `created_at_pms`, `guest_count`, fare, and a minimized `raw_json`. It does not write hometown or adult/child splits. Inquiries are stored and do not book nights (audit F1).

## Analyses and minimum samples

At 3 homes, a year of peak-season sales might be a few dozen stays. Rules of thumb used here (not a law):

| Analysis | Minimum before a claim is more than a hint | With today’s 47 confirmed stays |
|---|---|---|
| LOS by season | 30 stays in that season | Not met for winter. June–December only. |
| Lead-time distribution | 50 stays | 47. Usable as a wide prior, not a segment split. |
| Inquiry conversion by quoted price | 100 inquiries with a recorded quote and an outcome | 40 inquiries, outcomes not linked. **Unknown.** |
| Origin mix by season | 30 stays with city/state | Field not stored. **Unknown.** |
| Repeat guests | A pseudonymous id over 2 seasons | Not stored, by design, until the contract allows a hash. |
| Cancellation hazard by lead time | 30 cancellations | 13 canceled rows in the copy (mixed sources). Too few to fit a hazard. Use a literature prior and sweep. |
| Twins versus Cloud 9 | 30 stays per home | Cloud 9 has 7. **Unknown.** |

What 3 homes cannot identify: market elasticity, competitor response, the share of international demand, or whether a price cut caused a booking. Those need the simulator’s controlled shocks plus, later, more seasons of as-of prices.

## Privacy design

Store city or region, state, country, adults, children, infants, pets, channel, dates, and a one-way pseudonymous guest key if the operator wants repeat detection. Never store name, email, phone, street address, or message text in the pricing DB. Retention: keep the minimized row as long as the reservation is needed for pacing and ceiling history (the booking itself is an accounting fact). Do not retain the Guesty raw guest object.

## What this changes

- `src/pms/sync.py` and `src/db/schema.sql`: new nullable columns only.
- `src/elasticity/__init__.py`: read Guesty inquiry rows.
- Simulator: segment draws, not live prices, until a flag wins.

## What to do next

1. Write `docs/research/GUEST_DATA_CONTRACT.md` and implement only those columns.
2. Add a test fixture shaped like a Guesty reservation with `numberOfGuests` and `hometown`, and assert names are dropped.

## Open questions

- Will the operator approve a pseudonymous repeat-guest hash?
- Should canceled-after-confirm rows be labeled in replay (audit A9)? Yes, in Phase 3, with the thin-sample caveat.
