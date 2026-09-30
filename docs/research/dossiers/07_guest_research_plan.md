# Dossier 7 — Guest research the operator can run

Date: 2026-09-29
Access date: 2026-09-29

This is a plan, not a survey that was fielded. No guest was contacted.

## Why

Forty-seven stays cannot separate “they paid the ceiling because the week was Christmas” from “they would have paid it in a dry January.” A short post-stay instrument plus a coding of inquiry topics (aggregated, not stored raw in the pricing DB) is the honest way to set segment shares that dossier 1 had to assume.

## Instrument (10 questions)

Send only to guests who booked and completed a stay, after checkout, with a stated purpose and a way to refuse. Do not put names in the pricing DB. Store counts.

1. What was the main reason for this trip? (ski together / one family holiday / several families / couple / wedding or event / work retreat / other)
2. How many adults, children, and separate households slept here?
3. Where did you travel from? (city and state, or country — not street)
4. What else did you price? (another Winter Park home / a condo / a hotel / another resort / nothing)
5. When did you start looking? (this week / 2–3 weeks / 1–2 months / more than 2 months)
6. What almost stopped the booking? (price / dates / snow forecast / the drive / the house itself / nothing)
7. If the house had been about 10% more for the same dates, what would you have done? (booked anyway / booked fewer nights / picked another house / not come)
8. If it had been about 10% less, would you have booked earlier, longer, or the same?
9. How did you find the house? (Airbnb / VRBO / Google / friend / past stay)
10. May we use these answers, without your name, to set prices? (yes / no)

Question 7 is a rough Gabor–Granger probe at one price point, not a full van Westendorp (which needs four price questions and a larger sample). Van Westendorp and full conjoint need on the order of 100+ completed responses before a segment WTP is stable. **That sample size is a planning assumption, not a citation to a Winter Park study.** With three homes, one season of post-stay surveys might yield 20–40 responses. That can correct a segment **label**, not a price coefficient.

## Review mining

Code public review text (already public) into: group type, snow mention, drive or airport mention, value complaint, “booked for the holiday.” Do not pull reviewer names into the DB. Taxonomy feeds the simulator’s segment labels as **suggestive** until the counts are large.

## Inquiry coding

If the operator exports inquiry topics (dates, length, group size, “too expensive”) with names stripped, code the same taxonomy. Do not store message bodies in `wp_pricing.db`.

## Incentives and consent

A small credit on a future stay is a cost and a bias (respondents who want to return). Prefer no incentive for the first season, and report the response rate. Colorado guests are covered by the CPA’s rights of access and deletion; keep the survey file outside the pricing DB and honor deletion by dropping that response. https://coag.gov/resources/colorado-privacy-act/

## How outputs enter the model

- Segment shares and lead-time hints update `SIM_PARAMETERS.md` **before** the next evaluation, in a dated revision, not silently.
- Question 7’s “booked anyway” rate is a willingness check on the peak ceiling. It does not replace M1.
- Revealed prices (what they paid) stay the primary data. Survey WTP is an upper bound people overstate. If they disagree, trust the booking.

## What to do next

The operator runs this. The engine does not email guests.

## Open questions

- Is a post-stay note something the operator will actually send?
- Should past guests be asked, or only stays from the next season, so the ask is in the listing’s confirmation flow?
