# Independent test prompt — profitability under uncertainty

Audit `wp-price profitability-uncertainty` as an independent test agent. Do not modify pricing policy, calibration, Guesty credentials, owner data, `imports/private/`, or canary artifacts. The objective is to prove it is a conservative, reproducible decision aid—not a route for fabricated data to appear as actual profitability.

## Setup

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Use a temporary directory for all artifacts. Do not write an audit report into an owner-facing report path.

## Required checks

1. Run `pytest -q tests/profitability/test_uncertainty.py tests/data_spine/test_owner_net_scorecard.py`.
2. Run `wp-price profitability-uncertainty --out "$(mktemp -d)/report.md"`. It must exit `3`, emit `Guesty writes: 0` and `Data-spine writes: 0`, and the report must contain `ASSUMPTION-BASED`, `not settled owner net`, and `DO_NOT_SCALE_WITHOUT_NARROWER_SCOPE`.
3. Independently verify all scenario arithmetic: `booked = sellable × occupancy`; `incremental = sellable × incremental/net/night`; `net after system = incremental − system cost`; `break-even = cost / sellable`. The checked-in downside must be `900 × -$5 − $60,000 = -$64,500` and `$60,000 / 900 = $66.67`.
4. Copy the YAML to a temporary path and confirm fail-closed exit `2` for `data_classification: SETTLED-ACTUAL`; a missing `incremental_owner_net_per_available_night_usd`; occupancy above 1; and a non-negative price elasticity.
5. Prove isolation: the command has no database option; it creates no database, modifies no `imports/private/` content, imports no PMS/Guesty code in `src/profitability/`, and no result can enter owner-net, shadow, experiment, or canary workflows.
6. Review source semantics: public market data must be cited as aggregate context, while portfolio ADR, fees, costs, sellable nights, elasticity, and lift remain assumptions/ranges. No text may call these values settled or realized.
7. Run `pytest -q` and `mypy src`. Separate pre-existing failures from new ones.

## Deliverable

Report commands and exit codes, arithmetic, isolation and labeling evidence, test results, defects, and one verdict: `PASS`, `FAIL`, or `BLOCKED`. A PASS must explicitly say the model does not prove actual profitability and cannot authorize rate writes.
