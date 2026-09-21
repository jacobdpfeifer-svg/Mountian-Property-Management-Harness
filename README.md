# Mont Luxe Collection STR Pricing & Optimization Engine

Rules-first RevPAN optimizer for Mont Luxe Collection's three luxury homes in the
Winter Park / Fraser market: 312 Northwoods, 300 Northwoods, and Cloud 9.
Guesty is the system of record and Airbnb is a connected distribution channel.

**Not a Vantory clone.** Ceiling-relative pricing, leakage detection, and explainable recommendations — sized for a small portfolio, owned code, markdown-governed policy.

## Locked v1 decisions

Confirmed by the operator 2026-08-27. Full detail in `docs/LOCKED_INPUTS.md`.

| Input | Choice |
|---|---|
| System of record | **Guesty** Open API (live, syncing); CSV/iCal demo-only |
| Comp data | **Scraper-first** market sweep (built); AirDNA/Key Data hybrid in reserve |
| History | 6–12 months — one ski season, no year-over-year |
| Objective | **RevPAN**, by maximizing `P × P(book\|P)` |
| Authority | **Auto-push within guardrails**, gated on measured data health |

Ownership is explicit in `config/portfolio/mont_luxe.yaml`: 312 and 300
Northwoods share one owner; Cloud 9 is a separate owner. This separation is
used for reporting and is not a pricing advantage granted to either property.

## Quick start

```bash
cd "Harness for my wonderful Mother"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Init DB + load sample data
wp-price init-db
wp-price seed-sample

# Pull the real portfolio from Guesty (needs .env — see .env.example)
wp-price sync-guesty

# Curate a comp set from the live Winter Park market
wp-price discover-comps --date 2026-12-18 --min-price 400

# Refresh comp + whole-market prices (daily; non-zero exit if degraded)
wp-price scrape-comps --horizon 120

# Daily pacing capture — RUN THIS EVERY DAY, BEFORE INGEST.
# Skipped days are permanently unrecoverable.
wp-price snapshot

# What autonomy level does current data health grant?
wp-price health

# Generate explainable recommendations
wp-price recommend --from 2026-12-01 --to 2026-12-14

# Auto-push within guardrails (refuses unless health grants 'handle')
wp-price push --from 2026-12-01 --to 2026-12-14 --adapter dry_run

# RevPAN report vs actuals
wp-price report --from 2025-12-01 --to 2026-03-31
```

## Layout

```
docs/ARCHITECTURE.md     Locked architecture
docs/LOCKED_INPUTS.md    Operator-confirmed inputs (authoritative)
docs/rules/              Pricing doctrine, autonomy ladder, comp data (markdown)
config/policies/         Floors, curves, elasticity, guardrails, events (YAML)
src/ingest/              CSV / iCal adapters (idempotent)
src/pms/                 PMS adapter interface + rate writer (Guesty/Hostaway/dry-run)
src/pacing/              Daily pacing snapshotter
src/features/            Nightly feature builder
src/pms/                 Guesty client, sync, adapters, rate writer
src/scrape/              Market sweep, parsing, validation, run audit
src/comps/               Comp-set evidence with freshness + coverage
src/ceiling/             Season-scoped ceiling engine
src/bookprob/            Pooled booking-probability model
src/leakage/             Peak / shoulder / orphan-gap scanners
src/elasticity/          First-party conversion override
src/compose/             E[RevPAN] optimizer
src/guardrails/          Hard invariants + data-health autonomy gate
src/explain/             Reason taxonomy ranked by dollar contribution
src/eval/                Outcomes + RevPAN report
src/db/                  Schema + connection helpers
data/sample/             Demo CSVs / iCal
```

## Core metric

**RevPAN** = revenue ÷ available nights (blocked nights excluded). ADR and occupancy are
diagnostics, not co-equal optimizers.

Operationally that means price is chosen by maximizing `P × P(book|P)` over
`[floor, ceiling]` — not by chaining multipliers. Every recommendation carries the
booking probability and expected RevPAN behind it.

## Comp data

One market-wide search sweep per date window returns every bookable Winter Park /
Fraser listing with a parseable nightly rate (~280 listings), so Cloud 9 and the
twins share one daily `wp-price scrape-comps` job (`scripts/daily_scrape.sh`,
07:00 launchd). Comp membership is the post-sweep filter. Sweeps are validated
against constant-parser and blocked-sweep signatures and discarded wholesale if
suspect; `scrape_status` separates "checked and unavailable" from "could not check".
Details in `docs/rules/COMP_DATA.md` and `docs/CLOUD9_RUNBOOK.md`.

Install the scraper extra: `pip install -e ".[dev,scrape]"`.

## Safety model

Autonomy is **computed from data health every run**, never configured per run. Stale
comps, thin pacing history, or a low-confidence ceiling automatically demote `handle`
(writes rates) to `suggest` (writes nothing). Hard invariants — move caps, sanity floor,
peak-night blackout, run-scope cap — cannot be overridden at any level. See
`docs/rules/AUTONOMY.md`.

## License

Private / internal use for the operating portfolio unless otherwise stated.
