# Autonomy ladder

Mont Luxe Collection's own design: authority is earned per-rule, not switched on
globally.

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

### Grace period before demotion (amended 2026-09-20)

The configured `data_health.demotion_grace_runs` value implements a short grace period: a
gate has to fail for `N` consecutive runs before the demotion actually takes effect, so
one transient scrape hiccup or a one-off stale pull doesn't suggest-only an otherwise-
healthy run. A scope with no prior health history fails closed until it establishes a
healthy baseline. This does **not** loosen
any individual threshold (`pms_max_staleness_hours`, `comp_min_coverage`, etc.) or make
the level a stored setting again — it only adds hysteresis to *how many consecutive bad
readings* it takes before the computed level changes. The hard invariants below are
unaffected regardless of grace-period state; they apply to every push whether the run is
freshly demoted or not.

Once a demotion does trigger, recovery back to `handle` should still require a genuinely
healthy run (no equivalent grace period on the way back up) — the asymmetry is
deliberate: slow to demote a hair-trigger on noise, but not slow to re-arm real autonomy.

## Hard invariants

No level, and no config, may override these (`src/guardrails/apply_guardrails`):

- `max_increase_pct` / `max_decrease_pct` per night per run
- `max_abs_move` absolute dollar cap
- `sanity_min_ratio_to_anchor` — a price far under the seasonal anchor is a bug, not a bid
- `sanity_max_ratio_to_anchor` (added 2026-09-20) — a price far *over* the seasonal
  anchor is also a bug, not a bid. Checked on the price actually being returned,
  after the listed-price move cap, not just on the model's raw proposal — a
  corrupted `listed` price (bad PMS sync, unit mismatch, fat-fingered entry) can
  otherwise pull the move-cap band itself up to whatever the bad number implies,
  which a same-side-only floor check cannot catch
- `auto_push_blackout_demand_strength` — the highest-demand nights always escalate
- `max_nights_changed_per_run` / `max_pct_of_open_nights_per_run` — a run that wants to
  move most of the calendar is more likely a data fault than an opportunity; the largest
  moves are withheld first

Price rounding is **conservative**: it rounds toward the current listed price so the
$5 grid can never round a price past a cap.
