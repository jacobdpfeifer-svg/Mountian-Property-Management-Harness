# Pfeifer Optimization runbook

## SQI kill switch

If conditional ceilings misbehave against live inventory, revert to the
pre–Pfeifer Optimization stationary engine in one line:

```yaml
# config/policies/conditions.yaml
sqi:
  enabled: false
```

Then re-run `wp-price recommend`. No rebuild required.

`f(SQI)` is a **declared prior** with wide bands — not a fitted finding. One drought
season is n=1. Backtest intervals are intentionally wide.

## Agents never touch price

Collectors/extractors write observations. Feature builders write features.
Only the guarded pricing engine writes recommendations.

## Leak-free reads

Every `SignalStore.read_*` call requires `as_of` and filters `observed_at <= as_of`.

## Daily cycle

```bash
wp-price signals cycle --as-of 2026-08-29
wp-price signals brief
wp-price signals scoreboard
```
