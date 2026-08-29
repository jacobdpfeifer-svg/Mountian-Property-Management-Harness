# Signal Foundry runbook

Canonical operations live in
[`docs/PFEIFER_OPTIMIZATION_RUNBOOK.md`](PFEIFER_OPTIMIZATION_RUNBOOK.md)
(Pfeifer Optimization is the product name for this signal stack).

## SQI kill switch

```yaml
# config/policies/conditions.yaml
sqi:
  enabled: false
```

Then re-run `wp-price recommend`. No rebuild required.

`f(SQI)` is a **declared prior** with wide bands — not a fitted finding.

## Phase-2 live sources (unverified until parsers land)

CDOT (Berthoud / CoTrip), resort HTML extractors, and STR licence portals
return `quality=unavailable` with `value=None` when no fixture or wired
parser is present. **Do not invent zeros or estimates.** Re-verify live only
after a machine-readable source or extractor is connected.

## Daily cycle

```bash
wp-price signals cycle --as-of 2026-08-29
wp-price signals brief
wp-price signals scoreboard
```
