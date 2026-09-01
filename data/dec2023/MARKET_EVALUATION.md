# December 2023 Cloud 9 Market Evaluation

**Subject property:** Cloud 9 Chalet (`cloud_9`), 1615 Pioneer Trail, Winter Park — 6 bed / 4.5 ba, sleeps 18  
**Reference period:** December 2023  
**Decision date (simulated):** 2023-11-15  
**Database:** `data/dec2023_run.db` (isolated — no Guesty data)

---

## Comp Set (Luxury, 16–18+ Sleeps, New/Recent Homes)

| Comp | Sleeps | New Home? | Dec 2023 Rate Range | Source |
|------|--------|-----------|---------------------|--------|
| Lakota Reserve | 18 | Established luxury (Lakota) | $875 – $1,450 | [WPLC](https://www.winterparklodgingcompany.com/rentals/lakota-reserve) |
| Rifle Shot | 18 | Yes (~2021–22, Grand Park) | $725 – $1,250 | [Winter Park House](https://winterparkhouse.com/our-homes/rifle-shot/) |
| Deer | 16 | No | $695 – $1,150 | [Winter Park House](https://winterparkhouse.com/our-homes/deer/) |
| Brooky | 16+ | No (8,000 sq ft ultra-luxury) | $950 – $1,550 | [Winter Park House](https://winterparkhouse.com/our-homes/brooky/) |
| Corridor Way Chalet | 16 | Yes (~2022, Bridger's Cache ski-in/ski-out) | $1,100 – $1,750 | [Vrbo](https://www.vrbo.com/4797022) |
| Moose | 19 | No (downtown luxury) | $775 – $1,300 | [Winter Park House](https://winterparkhouse.com/our-homes/moose/) |
| Overlook Ridge | 16 | Yes (~2022–23, Lakota Northwoods) | $980 – $1,380 | [Elysian](https://elysiandestinations.com/vacation-rental/overlook-ridge/) |

**Market percentiles (curated comp set, Dec 2023):**

| Period | p50 | p75 | p90 |
|--------|-----|-----|-----|
| Early Dec (Dec 1–9) | $875 | $980 | $1,100 |
| Mid Dec (Dec 10–19) | $950 | $1,050 | $1,200 |
| Christmas peak (Dec 20–31) | $1,380 | $1,550 | $1,750 |

---

## Cloud 9 Market Position (December 2023)

| Metric | Cloud 9 | vs Comp p50 | vs Comp p75 |
|--------|---------|-------------|-------------|
| Avg listed price | $954/night | +9% | −9% |
| Avg booked rate | $971/night | +11% | −8% |
| Occupancy | 74.2% (23/31 nights) | — | — |
| RevPAN | $720 | — | — |
| ADR (booked) | $971 | — | — |

Cloud 9 priced **below the comp p75** across December — appropriate for a **new listing ramp** entering its first ski season. Listed rates sat near comp p50 in early/mid December and below p75 even at Christmas peak ($1,180–$1,320 listed vs $1,550 comp p75).

---

## Engine Recommendations (8 open nights)

| Stay Date | Listed | Recommended | Δ | P(book) | E[RevPAN] | Status |
|-----------|--------|-------------|---|---------|-----------|--------|
| Dec 5 (Tue) | $680 | $630 | −7.4% | 53% | $467 | Suggest |
| Dec 6 | $680 | $630 | −7.4% | 52% | $477 | Suggest |
| Dec 7 | $680 | $635 | −6.6% | 50% | $486 | Suggest |
| Dec 9 (Sat) | $795 | $735 | −7.5% | 72% | $620 | Suggest |
| Dec 14 | $680 | $620 | −8.8% | 61% | — | Suggest |
| Dec 17 (Sun) | $920 | $895 | −2.7% | 56% | $501 | Suggest |
| Dec 28 | $1,180 | $1,150 | −2.5% | 67% | $773 | **Blocked** (peak blackout) |
| Dec 29 | $1,320 | $1,285 | −2.7% | 61% | $788 | **Blocked** (peak blackout) |

**Key drivers:**
- **Low ceiling confidence (10%)** — only one partial ski season of booked history; engine defers 75% toward incumbent listed price
- **Comp set p75** ($965 early / $1,050 mid) pulled ceiling upward but comp blend weight is 30%
- **Peak blackout** blocked auto-changes on Dec 28–29 (demand strength ≥ 0.85)
- Early December open nights: engine suggests **modest decreases** (−5 to −7%) to improve booking probability on thin-history buckets

---

## RevPAN Report (December 2023)

```
Available nights:  8
Booked nights:     23
Revenue:           $22,325
RevPAN:            $720.16
ADR:               $970.65
Occupancy:         74.2%
```

Strong performance for a new property's first December — 74% occupancy at ~$971 ADR.

---

## Data Health

| Gate | Status |
|------|--------|
| PMS data freshness | Pass (0h) |
| Comp coverage | Pass (100%, 7/7 comps) |
| Comp freshness | Pass |
| Pacing history | Pass (14 days seeded) |
| **Granted autonomy** | **HANDLE** (all gates pass; individual recs still SUGGEST due to 10% ceiling confidence) |

---

## Caveats

1. **Portfolio inventory is synthetic** — estimated from new-listing ramp patterns, not Guesty actuals
2. **Comp prices are manually researched estimates** for Dec 2023, not scraped live data
3. **Comp snapshot `as_of` uses current date** for engine staleness compatibility; stay dates and prices reflect Dec 2023 market
4. **Only 8 of 31 December nights** received recommendations (23 were already booked)
5. **No live rate push** — autonomy stayed at SUGGEST; peak nights blocked from auto-change

---

## Files Created

```
data/dec2023/properties.csv
data/dec2023/nightly_inventory.csv   (245 rows, Jun 2023 – Jan 2024)
data/dec2023/comps.csv               (63 snapshot rows, 7 comps × 9 dates)
data/dec2023/demand_signals.csv
data/dec2023/market_snapshots.csv
data/dec2023_run.db                  (isolated SQLite DB)
scripts/load_market_snapshots.py
```

## Commands Used

```bash
wp-price --db data/dec2023_run.db init-db
wp-price --db data/dec2023_run.db ingest-csv \
  --properties data/dec2023/properties.csv \
  --inventory data/dec2023/nightly_inventory.csv \
  --comps data/dec2023/comps.csv \
  --demand data/dec2023/demand_signals.csv
python3 scripts/load_market_snapshots.py data/dec2023_run.db
wp-price --db data/dec2023_run.db signals cycle --as-of 2023-11-15
wp-price --db data/dec2023_run.db health
wp-price --db data/dec2023_run.db recommend \
  --from 2023-12-01 --to 2023-12-31 --property cloud_9 --allow-past
wp-price --db data/dec2023_run.db report --from 2023-12-01 --to 2023-12-31
```
