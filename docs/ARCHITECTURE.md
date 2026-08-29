# Architecture — Winter Park STR Pricing Engine

Locked for v1. See also the research plan that produced this design.

## Philosophy

```
v1 (now):      Rules + season-scoped ceiling + pooled linear-demand booking model,
               E[RevPAN] argmax under hard guardrails, autonomy gated on data health.
v1.5:          Pfeifer Optimization — condition-conditioned history (SQI). Agents write
               observations; deterministic features; guarded engine alone prices.
v2 (~6 mo):    Replace pooled linear demand with logistic regression per date-bucket
               once pacing_snapshots holds a full season (~40k observations).
v3 (optional): Length-of-stay optimization; min-stay as a decision variable.
```

**Drought reframing.** Last season's ~$482 Christmas was correct pricing under a
60%-of-normal snowpack (Berthoud Summit SNOTEL), not a mistake. The stationarity
assumption in raw-history ceilings is retired. See `config/policies/conditions.yaml`
and `docs/PFEIFER_OPTIMIZATION_RUNBOOK.md` (SQI kill switch).

**Sequencing note.** The binding constraint at 4 doors is data capture, not model
sophistication. `pacing_snapshots` must accumulate from day one — it is the only path
from ~1,460 property-nights/yr to a dataset a real model can use, and every day it
does not run is permanently lost. Pfeifer Optimization makes that data condition-tagged.

## Layers

1. **Ingest** (`src/ingest`, `src/pms`) — PMS API (Guesty/Hostaway) primary; CSV/iCal
   fallback. All loaders idempotent.
2. **Pacing** (`src/pacing`) — daily immutable snapshot of on-the-books state per
   `(property, stay_date, days_out)`. Run daily; skipped days are unrecoverable.
3. **Features** (`src/features`) — DOW, lead-time bucket, season, demand strength,
   orphan-gap flags, min-stay.
4. **Comps** (`src/comps`) — comp-set percentile per night, carrying freshness and
   coverage. Treated as an unreliable dependency.
5. **Ceiling** (`src/ceiling`) — season-scoped percentile, blended toward the seasonal
   anchor by confidence and toward comps by health. No cross-season fallback.
6. **Booking probability** (`src/bookprob`) — pooled beta-binomial base rate x linear
   demand with per-season elasticity. This is what makes RevPAN an objective.
7. **Leakage** (`src/leakage`) — peak underprice, shoulder over-discount, orphan gaps
   (with the min-stay lever).
8. **Compose** (`src/compose`) — maximize `P x P(book|P)` over `[floor, ceiling]`.
9. **Guardrails** (`src/guardrails`) — hard invariants + data-health-derived autonomy.
10. **Explain** (`src/explain`) — reasons ranked by signed dollar contribution.
11. **Eval** (`src/eval`) — outcomes, and an E[RevPAN] delta computed only over nights
    whose recommendation actually reached a channel.

## Out of scope (v1)

EBITDA / EV / exit readiness, owner attrition, marketing CTR product, channel-mix
automation, SaaS multi-tenant, Aerosolve/Java, academic notebook forks as production code.

Comp scraping is **in** scope (operator chose scraper-first) but not yet implemented:
`src/comps` reads whatever is in `comp_snapshots` and reports coverage honestly, so the
system degrades to advisory rather than guessing while the scraper is built.

## Rule governance

- Doctrine lives in `docs/rules/*.md` (human intent).
- Machine-readable policy lives in `config/policies/*.yaml`.
- Every recommendation stores `rule_version`, `model_version`, `reasons`, and `inputs_hash`.
