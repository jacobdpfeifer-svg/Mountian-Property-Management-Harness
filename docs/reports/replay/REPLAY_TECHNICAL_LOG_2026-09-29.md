# Technical process log — point-in-time replay (2026-09-29)

Operator-facing narrative: [`REPLAY_SUMMARY_2026-09-29.md`](REPLAY_SUMMARY_2026-09-29.md).  
This file is the exhaustive appendix: commands, files reviewed, and artifacts.

**CWD:** `/Users/jacobpfeifer/Library/Mobile Documents/com~apple~CloudDocs/Desktop/Harness for my wonderful Mother`  
**HEAD:** `f5918117d18d0fa56e69e1d862646338ddeb688b` (`feature/point-in-time-replay`)  
**Operator DB:** `data/wp_pricing.db` (symlink) → `/Users/jacobpfeifer/Library/Application Support/wp-price/data/wp_pricing.db` (12,476,416 bytes)

---

## 1. Commands (in order)

### 1.1 Planning-phase (2026-09-29 ~12:36 local, read-only)

These ran before the approved execution pass. Exit 0 unless noted.

```text
git rev-parse --abbrev-ref HEAD && git log -1 --oneline && git branch -a | rg -n "point-in-time"
# stdout: feature/point-in-time-replay / f591811 ... / remotes/origin/feature/point-in-time-replay
ls -la data/wp_pricing.db
# symlink -> ~/Library/Application Support/wp-price/data/wp_pricing.db
ls /tmp/testrun_*.db
# /tmp/testrun_cloud_9.db, testrun_overlook_ridge.db, testrun_summit_haus.db
```

Python inventory of candidate DBs (URI `mode=ro`): operator DB had 32,170 pacing rows; `/tmp/testrun_*.db` failed `unable to open database file` via URI in one planning query, later `ls` showed sizes 4,173,824 / 4,411,392 / 4,374,528. Operator DB chosen as the largest pacing history.

### 1.2 Execution — git

```bash
git fetch && git checkout feature/point-in-time-replay && git log -1 --oneline && git rev-parse HEAD
```

**Exit:** 0  

**Stdout (abridged):** fetched new remote branches unrelated to this work; `Already on 'feature/point-in-time-replay'`; working tree had unrelated local modifications (operator_surface / memory / receipt); `Your branch is up to date with 'origin/feature/point-in-time-replay'.`  
`f591811 Add honest point-in-time replay; fix bookprob leak and rigged counterfactual`  
`f5918117d18d0fa56e69e1d862646338ddeb688b`

Did not merge, commit, push, or alter Guesty.

### 1.3 Execution — tests

```bash
.venv/bin/python -m pytest tests/test_replay.py -q
```

**Exit:** 0  
**Stdout:** `........ [100%] 8 passed in 1.05s`  
Prompt expected 12 tests; this commit defines **8** `test_*` functions. Did not invent tests.

### 1.4 Execution — live inventory SQL

```bash
.venv/bin/python  # sqlite3 read-only against data/wp_pricing.db
```

**Exit:** 0  

Queries and raw results:

```sql
SELECT MIN(as_of), MAX(as_of), COUNT(DISTINCT as_of) FROM pacing_snapshots;
-- ('2026-08-18', '2026-09-29', 26)
```

```sql
SELECT as_of, COUNT(*) n, COUNT(DISTINCT property_id) props FROM pacing_snapshots GROUP BY 1 ORDER BY 1;
```

| as_of | n | props |
| --- | ---: | ---: |
| 2026-08-18 … 2026-09-01 (15 days, skip none except later) | 1098 each | 3 |
| 2026-09-03 | 1092 | 3 |
| 2026-09-20 | 1464 | 4 |
| 2026-09-21 | 1464 | 4 |
| 2026-09-22 | 1460 | 4 |
| 2026-09-23 | 1456 | 4 |
| 2026-09-24 | 1452 | 4 |
| 2026-09-25 | 1464 | 4 |
| 2026-09-26 | 1460 | 4 |
| 2026-09-27 | 1464 | 4 |
| 2026-09-28 | 1464 | 4 |
| 2026-09-29 | 1460 | 4 |

Distinct `as_of` (26):  
`2026-08-18` … `2026-09-01`, `2026-09-03`, `2026-09-20` … `2026-09-29`.  
**Clean window locked:** `2026-09-20`–`2026-09-29` (10 consecutive daily days). Backfill/gap block excluded from `--from/--to`.

```sql
SELECT property_id, COUNT(*) FROM pacing_snapshots GROUP BY 1 ORDER BY 1;
-- cloud_9 9506; creekside_haven 3652; overlook_ridge 9506; summit_haus 9506
```

```sql
SELECT COUNT(*), MIN(confirmed_at), MAX(confirmed_at) FROM reservations;
-- (88, '2026-05-12T01:50:31.518Z', '2026-09-25T17:06:07.420Z')
```

```sql
SELECT COUNT(*) FROM nightly_inventory WHERE booked_at IS NOT NULL;
-- 304
```

```sql
SELECT COUNT(*) FROM pacing_snapshots WHERE listed_price IS NOT NULL;
-- 31806
```

```sql
SELECT COUNT(*) FROM rate_changes;
-- 0
SELECT COUNT(*) FROM rate_changes
 WHERE result = 'applied' AND lower(COALESCE(actor, '')) LIKE '%guesty%';
-- 0
```

`/tmp/testrun_*.db` sizes: cloud_9 4,173,824; overlook_ridge 4,411,392; summit_haus 4,374,528 (smaller than operator 12,476,416). Not used for replay.

### 1.5 First replay spawn (failed)

```bash
mkdir -p docs/reports/replay && .venv/bin/python -m src.cli.main --db "data/wp_pricing.db" replay \
  --from 2026-09-20 --to 2026-09-29 --property summit_haus,overlook_ridge,cloud_9 \
  --horizon 365 --out docs/reports/replay
```

**Result:** tool `Command failed to spawn: Aborted`. No artifacts. Not retried as a blocking foreground 900s spawn.

### 1.6 Directory create

```bash
mkdir -p docs/reports/replay && echo "replay dir ready"
```

**Exit:** 0. **Stdout:** `replay dir ready`

### 1.7 Replay (succeeded)

```bash
PYTHONUNBUFFERED=1 .venv/bin/python -m src.cli.main --db "data/wp_pricing.db" replay \
  --from 2026-09-20 --to 2026-09-29 \
  --property summit_haus,overlook_ridge,cloud_9 \
  --horizon 365 --out docs/reports/replay \
  > docs/reports/replay/cli_stdout.log 2> docs/reports/replay/cli_stderr.log
```

**Wrapper PID:** 45516 (zsh). **Python PID:** 45522 (~99% CPU throughout).  
**Elapsed:** 1,383,878 ms (~23.1 min). **Shell exit:** 0.

**cli_stderr.log:** empty (0 bytes).

**cli_stdout.log (complete):**

```
Replayed 10 decision day(s) over 9644 night-decisions; censor 2026-09-29; Guesty writes=0
Calibration: measurable on 52 resolved nights (Brier 0.575)
  json: docs/reports/replay/replay_2026-09-29.json
  csv: docs/reports/replay/replay_2026-09-29.csv
  html: docs/reports/replay/replay_2026-09-29.html
EXIT:0
```

### 1.8 Post-run integrity / slice script

`.venv/bin/python` scoring the written CSV with `score_calibration` / `score_direction` / `estimate_revenue`, plus:

```sql
SELECT COUNT(*) FROM rate_changes; -- 0
SELECT COUNT(*) FROM rate_changes
 WHERE result = 'applied' AND lower(COALESCE(actor, '')) LIKE '%guesty%'; -- 0
SELECT DISTINCT as_of FROM pacing_snapshots
 WHERE as_of BETWEEN '2026-09-20' AND '2026-09-29' ORDER BY 1;
-- 10 dates matching result.decision_days
SELECT COUNT(*) FROM pacing_snapshots
 WHERE listed_price IS NOT NULL AND as_of BETWEEN '2026-09-20' AND '2026-09-29';
-- 14608
SELECT COUNT(*) FROM pacing_snapshots
 WHERE listed_price IS NOT NULL AND as_of BETWEEN '2026-09-20' AND '2026-09-29'
   AND property_id IN ('summit_haus','overlook_ridge','cloud_9');
-- 10956
```

### 1.9 Booked-vs-priced diagnostic (read-only; not a data repair)

```sql
SELECT property_id, stay_date, status, booked_at FROM nightly_inventory
 WHERE property_id IN ('summit_haus','overlook_ridge','cloud_9')
   AND stay_date <= '2026-09-29' AND booked_at IS NOT NULL
 ORDER BY stay_date DESC LIMIT 20;
-- parse_date(booked_at) succeeds (ISO timestamp [:10] → date)

SELECT COUNT(*) FROM nightly_inventory
 WHERE property_id IN ('summit_haus','overlook_ridge','cloud_9')
   AND stay_date <= '2026-09-29' AND booked_at IS NOT NULL;
-- 192

SELECT status, COUNT(*), SUM(booked_at IS NOT NULL)
 FROM nightly_inventory
 WHERE property_id IN ('summit_haus','overlook_ridge','cloud_9')
   AND stay_date BETWEEN '2026-09-21' AND '2026-09-29'
 GROUP BY 1;
-- available 9 / 0 booked_at; blocked 4 / 0; booked 14 / 14
```

Replay CSV: all **52** resolved rows have empty `booked_at`; `booked_by_censor` false on **9,644 / 9,644**. Finding: priced resolved nights ≠ inventory booked nights in that window. Did not change code or data.

### 1.10 Artifact listing

```bash
ls -l docs/reports/replay && wc -l docs/reports/replay/replay_2026-09-29.csv && git log -1 --format='%H %s'
```

**Exit:** 0. See §3.

---

## 2. Files reviewed

Planning + execution. Paths relative to repo root.

| Path | Why |
| --- | --- |
| `src/eval/replay.py` | Replay loop, Guesty refuse, `MIN_CALIBRATION_NIGHTS=20`, `MIN_DIRECTION_GROUP=5`, listed-price lookup, censor, HTML/JSON/CSV writers |
| `src/eval/shadow.py` | `guesty_write_count` predicate (`result='applied'` AND actor LIKE `%guesty%`); `GuestyWriteForbidden` |
| `src/cli/main.py` | `cmd_replay`, `--from/--to/--property/--horizon/--out`, print lines, `_resolve_scope`, `_guard_testrun_scope` |
| `src/db/__init__.py` | `DEFAULT_DB_PATH = data/wp_pricing.db` |
| `src/compose/__init__.py` | `generate_recommendations(..., persist=False, as_of=...)` (grep only) |
| `src/utils.py` | `parse_date` uses `str(value)[:10]` so ISO `booked_at` timestamps parse |
| `tests/test_replay.py` | 8 tests: scoring honesty, Guesty refuse, empty window, e2e reports, bookprob leak |
| `docs/reports/replay/replay_2026-09-29.html` | Provenance line, decision days, measured/estimated panels |
| `docs/reports/replay/replay_2026-09-29.json` | Score objects (rows not inlined here; 9,644 in file) |
| `docs/reports/replay/replay_2026-09-29.csv` | Per-property slices and `listed_source` / `resolved` counts |
| `docs/reports/replay/cli_stdout.log` | CLI stdout capture |
| `docs/reports/replay/cli_stderr.log` | Empty |

Grep during planning: `DEFAULT_DB_PATH`, `replay`, `guesty_write_count`, `def test_`, `_decision_days`, `_data_ceiling`, `_listed_as_of`, `estimate_revenue`, `_guard_testrun_scope`.

Not edited: policy YAML, elasticity betas, frozen CSV exports, existing `docs/reports/TESTRUN_*.md`.

---

## 3. Data the repo produced

### 3.1 Files (after replay, before these two markdowns)

| Path | Bytes | mtime (local) |
| --- | ---: | --- |
| `docs/reports/replay/replay_2026-09-29.json` | 3,771,398 | Sep 29 13:26 |
| `docs/reports/replay/replay_2026-09-29.csv` | 914,857 | Sep 29 13:26 |
| `docs/reports/replay/replay_2026-09-29.html` | 3,826 | Sep 29 13:26 |
| `docs/reports/replay/cli_stdout.log` | 308 | Sep 29 13:26 |
| `docs/reports/replay/cli_stderr.log` | 0 | Sep 29 13:03 |

CSV: **9,645** lines = 1 header + **9,644** data rows.

This log and `REPLAY_SUMMARY_2026-09-29.md` are additional new files in the same directory.

### 3.2 JSON score objects (rows omitted)

`generated_at`: `2026-09-29`  
`window_from` / `window_to`: `2026-09-20` / `2026-09-29`  
`censor_date`: `2026-09-29`  
`property_ids`: `["summit_haus", "overlook_ridge", "cloud_9"]`  
`warnings`: `[]`

`decision_days` (N=10):  
`2026-09-20`, `2026-09-21`, `2026-09-22`, `2026-09-23`, `2026-09-24`, `2026-09-25`, `2026-09-26`, `2026-09-27`, `2026-09-28`, `2026-09-29`  
Matches clean-window DISTINCT `as_of`.

`price_ref_note`:  
`Reference prices for older pool nights use today's listed price where no as-of pacing snapshot exists; those nights are not silently repaired.`

`ceiling` (whole-DB, as coded in `_data_ceiling`):

```json
{
  "decision_days": 10,
  "nights_with_pacing_listed": 31806,
  "pacing_max_as_of": "2026-09-29",
  "pacing_min_as_of": "2026-08-18",
  "reservations": 88
}
```

`calibration` (N eligible = 52):

```json
{
  "measurable": true,
  "eligible": 52,
  "brier": 0.5750282105523428,
  "bins": [
    {"lo": 0.0, "hi": 0.2, "n": 18, "mean_predicted": 0.09669352956611071, "observed_rate": 0.0},
    {"lo": 0.6000000000000001, "hi": 0.8, "n": 2, "mean_predicted": 0.7269804529010947, "observed_rate": 0.0},
    {"lo": 0.8, "hi": 1.0, "n": 32, "mean_predicted": 0.9447316662207838, "observed_rate": 0.0}
  ]
}
```

`direction`:

```json
{
  "measurable": true,
  "above_n": 18,
  "below_n": 34,
  "above_book_rate": 0.0,
  "below_book_rate": 0.0
}
```

`estimated_revenue`:

```json
{
  "measurable": true,
  "comparable_nights": 9623,
  "booked_by_censor": 0,
  "assumption": "bookings do not respond to price (price-swap only) — not a causal result",
  "bookings_unchanged": {"engine_revpan": 0.0, "listed_revpan": 0.0, "lift": 0.0},
  "engine_demand_model": {
    "engine_revpan": 17.853706423442386,
    "listed_revpan": 18.48860008234031,
    "lift": -0.6348936588979228
  }
}
```

### 3.3 CSV counts

| Slice | N |
| --- | ---: |
| All night-decisions | 9644 |
| summit_haus | 3121 |
| overlook_ridge | 3291 |
| cloud_9 | 3232 |
| `listed_source=pacing` | 9623 |
| `listed_source=none` | 21 |
| `resolved=True` | 52 |
| `resolved=False` | 9592 |
| `booked_by_censor=True` | 0 |
| `booked_by_censor=False` | 9644 |

Resolved stay_dates among 52: `2026-09-28` 24; `2026-09-29` 18; `2026-09-24` 4; `2026-09-23` 3; `2026-09-22` 2; `2026-09-21` 1.

Per-property scores (same functions as the engine, sliced):

| Property | n | listed none | cal eligible | cal | dir above/below |
| --- | ---: | ---: | ---: | --- | --- |
| summit_haus | 3121 | 7 | 17 | unmeasurable | 6 / 11, both book 0% |
| overlook_ridge | 3291 | 7 | 17 | unmeasurable | 12 / 5, both book 0% |
| cloud_9 | 3232 | 7 | 18 | unmeasurable | 0 / 18 unmeasurable |

### 3.4 Integrity

- CLI asserted `Guesty writes=0`.
- `rate_changes` empty (**0** rows) after the run.
- `persist=False` in `run_replay`; no `handle` / `set_rate`.
- `assert_no_lookahead` ran inside `run_replay` (run completed; would have raised otherwise).

### 3.5 What was not produced

- No Guesty writes.
- No edits to policy, betas, or existing `docs/reports/TESTRUN_*.md`.
- No per-property extra 365-day engine runs (plan: slice the combined CSV).
- No git commit.

---

## 4. Interpretation (not extra data)

Crystal-ball **framework** ran on real as-of days. Combined calibration met N=20 with **52** resolved priced nights, but **observed booking rate 0%** on that panel and **0 / 9,623** comparable nights booked-by-censor, so estimated bookings-held-fixed RevPAN is **$0**. That is a sample-construction finding (priced available nights vs inventory booked nights), not a market-beat. Grow resolved, actually-checked-in nights with daily `wp-price shadow-record`.
