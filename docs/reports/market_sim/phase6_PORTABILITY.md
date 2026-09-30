# Phase 6 — Portability

Date: 2026-09-29
Branch: `feature/market-sim-and-learning`

The second market is Telluride, Colorado. Dossier 6 ranked it first. This file is the portability spec: the list of what had to change, and nothing else was retuned.

## What changed

| Piece | Winter Park | Telluride |
|---|---|---|
| Resort YAML | `config/resort/winter_park.yaml` (`market_id: grand_home`, Intrawest feed id 5) | `config/resort/telluride.yaml` (`market_id: telluride`, `intrawest_feed_id: null`) |
| Season window | Simulator 2026-11-01 through 2027-04-29 | Targeted open 2026-11-26, close 2027-04-04. Source: https://tellurideskiresort.com/ski/ access 2026-09-29 |
| Signals | Winter Park SNOTEL / Berthoud / I-70 collectors stay pointed at Grand County | No station triplet. Red Mountain Pass is named as a candidate and `station_id` is null. Roads are Dallas Divide and Lizard Head; CDOT segment ids are UNVERIFIED |
| Scrape region | Existing Winter Park comp sweep | No Telluride scrape was run and no bbox was invented |
| Calibration | `proving_ground_exam/market/calibration.yaml` | `proving_ground_exam/market/portability/telluride_calibration.yaml` |
| Scenario | `proving_ground_exam/scenarios/normal.yaml` and the other 14 | `proving_ground_exam/market/portability/telluride_normal.yaml` |

`load_resort_config()` still reads the Winter Park file. Adding Telluride does not change `seed_resort_reference`.

Choice parameters (segment shares, logit slopes, arrival mean, WTP) are the Winter Park calibration copied across and labeled not re-fit. The three home ids are stand-ins with the same beds and base rates. They are not a Telluride listing.

The 15-scenario folder still has exactly 15 files. `test_telluride_portability_file_is_outside_the_fifteen` checks that.

Pass blackouts in the resort file are the limited-pass restricted dates from the ski FAQ (Dec 26–31 2026, Jan 1–2, Jan 16, Feb 13–14 2027), not Ikon dates. Wind gust 35 mph is not in this file as a measured threshold. Terrain opening order is marked assumed.

Airport: TEX primary, MTJ alternate. The fetched DEN–TEX schedule is a summer 2026 PDF (https://tellurideskiresort.com/wp-content/uploads/CFA_FlightSchedule_S26_Final.pdf). Winter frequency is UNVERIFIED.

## Simulator

Three flat-price seeds on `telluride_normal`, full published window, exit 0. Databases were deleted after scoring. JSON: `.testrun_runs/market_sim/telluride/flat_seeds.json`.

| Seed | Revenue | Confirmed | Occupancy | LOS | Lead ≤21 | Inquiry / confirmed | Early occupancy |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 186800 | 43 | 0.541 | 4.91 | 0.326 | 0.56 | 0.158 |
| 2 | 203250 | 50 | 0.592 | 4.62 | 0.480 | 0.70 | 0.368 |
| 3 | 170150 | 42 | 0.490 | 4.55 | 0.286 | 0.81 | 0.088 |

LOS and the inquiry ratio sit inside the Winter Park validation ranges. Lead time within 21 days misses the 0.40 floor on seeds 1 and 3, the same miss as the Winter Park flat world. Early occupancy on seed 3 is 0.088, under the 0.10 floor. Telluride's early window is only Nov 26–Dec 14, so that bucket is short. Parameters were not edited.

One engine seed (flags off, seed 1) finished on the same window: revenue $110,870, guardrail trigger count 1,406. Flat seed 1 on the same shoppers was $186,800. That is one seed, not a ranking. The trigger count includes every non-empty `guardrail_action`, and on Winter Park engine runs `peak_blackout` is most of that count. It is not 1,406 price-cap breaches. The database was deleted after the score was written, so this seed was not split by action.

## Tests

```
.venv/bin/python -m pytest -q tests/proving_ground/test_market_sim.py::test_fifteen_scenarios_and_held_out_names tests/proving_ground/test_market_sim.py::test_telluride_portability_file_is_outside_the_fifteen --tb=short
```

Both passed inside the market-sim file run (26 passed, 1 deselected, exit 0).

## Proven, suggestive, unknown

- **Proven.** A second market file can be scored without adding a 16th scenario and without changing the Winter Park calibration file.
- **Suggestive.** Flat-world occupancy on the shorter Telluride window is in the same band as Winter Park (about 0.49–0.59). That is the copied demand process, not a Telluride booking history.
- **Unknown.** What a Telluride scrape, a real SNOTEL triplet, or a winter flight schedule would do to the engine. None of those were collected.

## Deviations

No live scrape. No invented Intrawest feed id. The engine comparison is one seed. A paired interval was not computed.

## Open operator questions

Telluride was used because dossier 6 ranked it first. Say if the portability spec should be Steamboat instead. The home ids would still be stand-ins until there is a listing file.
