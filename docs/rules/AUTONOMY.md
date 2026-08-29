# Autonomy ladder

Adapted from Vantory's Watch / Suggest / Handle it / Escalate model, which is the
best idea on their site: authority is earned per-rule, not switched on globally.

| Level | Writes rates? | Meaning |
|---|---|---|
| `watch` | no | Observe and log only. |
| `suggest` | no | Queue recommendations for human approval. **Default.** |
| `handle` | **yes** | Auto-push within guardrails. |
| `escalate` | no | Something needs a human now; never pushed. |

## Autonomy is computed, not configured

`config/policies/default.yaml` sets `autonomy.max_level`. That is a **ceiling, not a
grant**. The level actually used each run is produced by `assess_data_health()` and is
demoted to `suggest` whenever any gate fails:

- PMS data older than `pms_max_staleness_hours`
- comp data older than `comp_max_staleness_hours`
- comp coverage below `comp_min_coverage`
- fewer than `pacing_min_snapshot_days` of pacing history
- ceiling confidence below `autonomy.require_ceiling_confidence` (per-night demotion)

**Why.** The operator chose scraper-first comp data *and* auto-push. Scrapers rarely
fail loudly; they return stale or partial data. A depressed comp reading feeding an
auto-push loop moves real rates on real inventory before anyone opens a dashboard.
Making the level a stored setting would mean one bad scrape day is enough. Making it a
function of measured health means the system degrades to advisory on its own.

Inspect with `wp-price health`. Every run's verdict is persisted to `data_health_runs`.

## Hard invariants

No level, and no config, may override these (`src/guardrails/apply_guardrails`):

- `max_increase_pct` / `max_decrease_pct` per night per run
- `max_abs_move` absolute dollar cap
- `sanity_min_ratio_to_anchor` — a price far under the seasonal anchor is a bug, not a bid
- `auto_push_blackout_demand_strength` — the highest-demand nights always escalate
- `max_nights_changed_per_run` / `max_pct_of_open_nights_per_run` — a run that wants to
  move most of the calendar is more likely a data fault than an opportunity; the largest
  moves are withheld first

Price rounding is **conservative**: it rounds toward the current listed price so the
$5 grid can never round a price past a cap.
