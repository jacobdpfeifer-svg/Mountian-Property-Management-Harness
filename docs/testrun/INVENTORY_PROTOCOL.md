# Owned forward inventory protocol (testruns)

**Locked 2026-09-25.** A Guesty-blind year cannot supply property-specific forward
calendars. Public Airbnb discovery often returns **proxy** listings. Those two
facts are why Summit and Overlook froze 0 recommendation rows.

## Decision

Diagnostic testruns use **read-only Guesty calendars as the owned-inventory
source**. Comp market sweeps stay independent. Guesty listed prices may enter
compose as the incumbent rate. They are not comps. Writes to Guesty remain
forbidden.

```bash
wp-price seed-forward-inventory \
  --property summit_haus \
  --source guesty-readonly \
  --db /tmp/testrun_summit_haus.db
```

`--source empty-skeleton` inserts availability rows with `listed_price` NULL
when an operator wants compose without an incumbent rate.

`wp-price recommend` now exits 2 with `0 available nights in scope` instead of
exporting an empty CSV.

## Proxy vs exact

After seed, start pacing with `wp-price snapshot` (optional `--backfill N` is biased).
Once recommendations exist, run forward shadow **daily** (local SQLite only; the
command refuses if `rate_changes` already contains a Guesty write):

```bash
wp-price shadow-record --property summit_haus --db /tmp/testrun_summit_haus.db
```

Keep Guesty live listed rates. Do not enable auto-push. Comp snapshots already store
`as_of` historically; do not overwrite them in place.
