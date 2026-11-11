# Profitability under uncertainty

Generate the model report with:

```bash
wp-price profitability-uncertainty --out /tmp/profitability-under-uncertainty.md
```

The checked-in model intentionally exits `3`: its downside case does not clear the hurdle. That is a conservative decision result, not a runtime failure. The command sends no request and performs zero Guesty or data-spine writes.

```text
annual incremental owner net = sellable nights × incremental owner net per available night
annual net after system cost = annual incremental owner net − annual system cost
```

It must not be represented as settled owner net, realized profit, evidence of pricing lift, or permission for a canary. See [the source register](../../research/PROFITABILITY_UNDER_UNCERTAINTY_SOURCES.md).
