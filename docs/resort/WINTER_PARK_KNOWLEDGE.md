# Winter Park Resort — operator knowledge

Human context for the machine-readable corpus in `config/resort/winter_park.yaml`.

## Data sources (free)

1. **Intrawest JSON feed** — primary live source for lift/trail status
   (`https://snowreporting.herokuapp.com/feed/5/lifts`). Same feed Liftie uses.
2. **Mountain report HTML** — fallback for base depth and ticket window.
3. **Berthoud Summit SNOTEL** — snowpack ground truth for terrain opening priors.
4. **Open-Meteo** — wind gust forecast for wind-hold risk on exposed lifts.
5. **CoTrip** — Berthoud Pass / US-40 access (distinct from on-mountain closure).

## Terrain opening sequence (typical)

Base area (Gondola, Discovery) opens first when snowmaking and natural snow allow.
Mary Jane bowls follow once SWE exceeds ~14". Eagle Wind and Parsenn need deeper
pack. **The Cirque is last** — usually mid-February or later, requires the highest SWE.

## Wind-hold lifts

Panoramic Express, Eagle Wind, Super Gauge, and Iron Horse are the most frequent
wind holds. When Open-Meteo forecasts gusts above 35 mph, the ops brief flags
elevated lift-hold risk — not a guarantee of closure.

## Snow packing

Early season surfaces are dominated by machine-made snow on thin natural base.
Mid-winter cold periods produce packed powder / granular surfaces. Spring warming
shifts toward corn and variable conditions. Live grooming coverage from the feed
adjusts the surface score alongside these month-based priors.

## Hiring signal

Winter Park posts lift-operator roles Aug–Oct. This is a **season-readiness prior**
only — we do not have live headcount. It nudges early-season terrain-open forecasts
when staffing ramp is underway.

## Ikon blackouts

Blackout dates change annually. Verify against [ikonpass.com](https://www.ikonpass.com)
each fall and update `config/resort/winter_park.yaml`.

## Historical events

Curated wind holds, Cirque openings, and season open/close dates live in the
`resort_events` table. Add new events as they occur — they improve wind-hold
frequency priors over time.
