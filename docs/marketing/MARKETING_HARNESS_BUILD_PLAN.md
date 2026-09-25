# Marketing Harness — Build Plan (Meta Ads)

**Status:** Proposed architecture. Not yet built. Companion to
`docs/marketing/META_ADS_STRATEGY_AND_RESEARCH.md` (read that first for the
"why" and the industry landscape).
**Date:** 2026-09-25.

This plan translates the strategy into a concrete buildout that **reuses the
existing harness's skeleton** — rules-first, markdown-governed policy, YAML
config, an autonomy ladder gated on measured data health, hard invariants that
cannot be overridden, and dollar-ranked explainability. The pricing engine
already proved that skeleton on real money. The marketing side is the *same
machine pointed at ad spend instead of nightly rates.*

---

## 1. The one-paragraph architecture

A **Meta lead/booking harness** ingests campaign performance and lead events
(via the Meta Marketing API / official MCP + CAPI), decides actions against
**markdown-governed doctrine** and **YAML guardrails**, and either **suggests**
or **auto-executes** (budget shifts, pauses, creative rotation, new launches)
depending on the **autonomy level computed from data health every run**. Every
action is **explainable and dollar-ranked**. A **compliance gate** (Fair Housing
/ Special Ad Category, TCPA consent) is a **hard invariant that fail-closes**.
Outcomes are read back from the **CRM** (signed doors / booked stays) and fed to
**CAPI** to optimize toward money, not form fills. A **speed-to-lead** responder
fires an instant, compliant follow-up on every lead.

## 2. How it maps onto what already exists

| Pricing harness (today) | Marketing harness (proposed) | Reuse |
|---|---|---|
| `src/pms/` Guesty client, rate writer | `src/marketing/meta/` Marketing API + MCP client, campaign/budget writer | Same "external system of record + gated writer" pattern |
| `src/scrape/` + `src/comps/` market evidence | `src/marketing/insights/` performance + benchmark evidence | Same freshness/coverage discipline |
| `src/pacing/` daily snapshotter | `src/marketing/pacing/` daily spend/lead/CPL snapshot | **Reuse directly** — same "skipped days unrecoverable" rule |
| `src/bookprob/` + `src/compose/` optimizer (`P × P(book\|P)`) | `src/marketing/optimizer/` allocate budget to maximize signed-doors / booked-revenue per $ | Same expected-value framing |
| `src/guardrails/` hard invariants + autonomy gate | `src/marketing/guardrails/` budget caps, CPL ceilings, frequency caps, **compliance gate** | **Reuse the gate engine**; add ad-specific invariants |
| `src/explain/` reason taxonomy, $-ranked | `src/marketing/explain/` reason per campaign action, $-ranked | **Reuse directly** |
| `src/eval/` RevPAN report vs actuals | `src/marketing/eval/` cost-per-door / ROAS / cost-per-booking vs actuals | Same outcomes framing |
| `docs/rules/*.md` doctrine (PRICING_DOCTRINE, AUTONOMY, COMP_DATA) | `docs/rules/AD_DOCTRINE.md`, `AD_AUTONOMY.md`, `COMPLIANCE.md`, `CREATIVE_DOCTRINE.md` | Same markdown-governed policy |
| `config/policies/*.yaml` | `config/marketing/*.yaml` (budgets, guardrails, audiences, per-client) | Same YAML-config pattern |
| `config/portfolio/mont_luxe.yaml` | `config/clients/<client>.yaml` (each PM client scoped, like owner-scoping) | Same scoping/isolation model |

**The point:** ~60–70% of the marketing harness is the *same engine*. We are not
building a new product from scratch; we are adding a new "domain adapter" plus a
compliance gate and a creative loop.

## 3. Proposed module layout

```
src/marketing/
  meta/            Marketing API + Conversions API client; wraps official MCP where possible
  mcp/             Adapter to official Meta Ads MCP (mcp.facebook.com/ads) + fallback third-party
  insights/        Pull spend/CPL/CTR/ROAS/frequency; benchmark evidence with freshness
  leads/           Lead retrieval (webhook + polling); dedupe; consent capture/audit
  capi/            Server-side events + offline conversions (form → CRM outcome → Meta)
  crm/             Connectors: LeadSimple (primary), Follow Up Boss; read "did lead → door?"
  creative/        Angle/script generation, variant orchestration (Arcads/AdCreative/Advantage+), scoring, rotation
  audiences/       Custom audiences (guest/owner email lists), retargeting, Special Ad Audiences (compliant)
  compliance/      Special Ad Category classifier + TCPA consent gate (HARD INVARIANT, fail-closed)
  optimizer/       Budget allocation + bid/pacing rules (expected-value; consolidate, don't fragment)
  speed_to_lead/   Instant compliant responder (email default; SMS only w/ logged consent)
  pacing/          Daily spend/lead snapshot (reuse pattern from src/pacing/)
  guardrails/      Budget caps, CPL ceilings, frequency caps, autonomy gate (reuse src/guardrails/)
  explain/         Dollar-ranked reasons per action (reuse src/explain/)
  eval/            Cost-per-door / ROAS / cost-per-booking vs actuals

config/marketing/
  default.yaml          Global guardrails, CPL ceilings, frequency caps, refresh cadence
  clients/<client>.yaml Per-client: objective, budget, audiences, compliance class, CRM creds ref

docs/rules/
  AD_DOCTRINE.md        Campaign structure, budget consolidation, creative volume doctrine
  AD_AUTONOMY.md        The suggest→handle ladder for ad ops + data-health inputs
  COMPLIANCE.md         Fair Housing / Special Ad Category + TCPA — hard invariants
  CREATIVE_DOCTRINE.md  Angles, refresh cadence, UGC standards, scoring

docs/marketing/
  META_ADS_STRATEGY_AND_RESEARCH.md   (this brief's companion)
  MARKETING_HARNESS_BUILD_PLAN.md     (this file)
```

## 4. The autonomy ladder for ad ops (mirror the pricing gate)

Same principle: **autonomy is computed from data health every run, never
configured per run.** Stale or thin signal automatically demotes `handle` (writes
changes) to `suggest` (writes nothing).

| Level | What it does | Gated on (data health inputs) |
|---|---|---|
| `observe` | Read-only reporting + alerts | Always available |
| `suggest` | Proposes budget/creative/pause actions for human approval | Pixel + CAPI firing; ≥ N days of pacing history |
| `handle` | Auto-executes **within guardrails** (budget shifts, pauses, creative rotation) | Above + CRM outcome loop connected + ≥ N conversions in learning + compliance gate green |

**Hard invariants that no level can override:**
- **Compliance gate** — renter/dwelling campaigns must prove Special Ad Category
  compliance or they do not launch (fail-closed). TCPA consent required before
  any automated SMS/call.
- **Budget invariants** — per-client daily cap, single-action budget-move cap,
  run-scope cap (mirror the pricing "move caps" + "run-scope cap").
- **CPL ceiling** — auto-pause a campaign that exceeds its CPL ceiling for M days.
- **Frequency cap** — auto-rotate/pause on creative fatigue (frequency > limit).
- **Account-safety floor** — never launch creative flagged by the policy linter.

## 5. Build vs. buy (decisions, not options)

| Capability | Decision | Why |
|---|---|---|
| Read spend/ROAS, update budgets, diagnostics | **Use official Meta Ads MCP** (`mcp.facebook.com/ads`, ~29 tools, Business OAuth) | No Dev App wait; agent-driveable; Meta-maintained |
| Launch campaigns, upload creative | **Marketing API directly** (+ third-party MCP e.g. Pipeboard as accelerator) | Official MCP is read/budget-heavy; need write path |
| CAPI / offline conversions | **Build thin `src/marketing/capi/`** over the API | Core moat (signal quality); must own it |
| Lead → CRM → CAPI plumbing | **Self-host n8n** | Owned data, matches repo ethos; templates exist |
| CRM | **Integrate LeadSimple** (then Follow Up Boss) | PM-native; never rebuild a CRM |
| Rule engine (pause/scale/alert) | **Own it** (extend `src/guardrails/`) | It's our moat + not hard; avoid per-seat SaaS lock-in. Revealbot only as a temporary Phase-1 crutch |
| AI creative rendering | **Orchestrate Arcads/AdCreative + Advantage+ Creative** | Rendering is commodity; the *angles + scoring + rotation* are ours |
| Compliance classifier | **Build** `src/marketing/compliance/` | The differentiator; nobody sells this for PM |
| Speed-to-lead responder | **Build thin**, consent-gated | Cheap 21x; must be TCPA-safe |

**Rule of thumb:** buy/borrow the commodity (rendering, CRM, MCP transport,
plumbing); build the governance, compliance, and signal-loop (the moat).

## 6. Phased rollout

### Phase 0 — Dogfood on Mont Luxe (STR direct bookings) — *no client, no risk*
- Connect the official Meta Ads MCP to the Mont Luxe ad account (read first).
- Stand up Pixel + CAPI on the direct-booking site; feed Guesty booking events.
- Build a **past-guest Custom Audience** from the existing email list; run a
  retargeting + lookalike-style direct-booking campaign to cut OTA commission.
- Implement `insights/`, `pacing/`, `compliance/` (classifier), `explain/` at
  `observe`/`suggest` only. Measure: booked-conversion + cost vs OTA-commission
  baseline. **Gate the whole pivot on this beating the baseline.**

### Phase 1 — Done-for-you door acquisition for 1–2 pilot PM clients
- Owner-lead campaigns (non-housing, full targeting + Lookalikes + CAPI).
- Instant Forms with **consent capture + audit trail**; leads → LeadSimple via
  n8n; speed-to-lead responder (email default).
- CRM outcome loop live: signed-agreement event → CAPI → optimize toward doors.
- Creative loop producing 20+ variants / refresh cycle; scored on outcomes.
- Harness runs at `suggest`; human backstops every action. Learn the real rules
  on real spend. Measure cost-per-signed-door vs. the client's baseline.

### Phase 2 — Productize (only after Phase 1 rules are proven)
- Promote proven campaigns to `handle` within guardrails.
- Multi-client scoping (`config/clients/*.yaml`), per-client isolation and
  reporting (mirror owner-scoping).
- Self-serve onboarding, billing, dashboards. Consider SaaS vs. managed-service.

## 7. What can be prototyped *today* in this environment

The official Meta Ads MCP is **not currently connected** to this session, but the
substrate is available to wire up. Concretely, near-term steps that need no new
product decisions:

1. Author the doctrine markdown (`AD_DOCTRINE.md`, `AD_AUTONOMY.md`,
   `COMPLIANCE.md`, `CREATIVE_DOCTRINE.md`) — same governance style as the
   pricing rules. **This is the cheapest, highest-leverage first commit.**
2. Draft `config/marketing/default.yaml` guardrail thresholds from the §3
   benchmarks in the strategy brief.
3. Scaffold `src/marketing/compliance/` — the Special Ad Category classifier is
   pure logic (imagery/intent → housing? → allowed targeting envelope) and is
   testable with no ad account.
4. Scaffold `src/marketing/pacing/` by lifting the existing `src/pacing/` pattern.
5. Connect the official Meta Ads MCP (Business OAuth) to a Mont Luxe test account
   and validate read-only `insights/` before writing anything.

## 8. Success metrics (so we know if it's working)

- **Phase 0:** direct-booking cost per booking < OTA commission saved; guest
  retargeting ROAS > 1 within one refresh cycle.
- **Phase 1:** cost-per-signed-door within/under the ~$77 owner-CPL benchmark
  *adjusted for close rate*; speed-to-lead median < 5 min; ≥ 1 door closed per
  pilot within the pilot window.
- **Phase 2:** doors added per $ of spend beats the client's prior channel mix;
  zero compliance incidents (no housing rejections, no TCPA complaints).

## 9. Open decisions for the operator

1. **Primary CRM** for pilots — LeadSimple (PM-native, recommended) vs. whatever
   the pilot client already runs (AppFolio/Buildium/Follow Up Boss).
2. **Managed-service vs. SaaS** end state (affects how much self-serve to build).
3. **SMS in speed-to-lead** — enable only with a hardened consent flow, or ship
   email-only for v1 to sidestep TCPA risk entirely.
4. **How much to internalize vs. lean on third-party MCP** (Pipeboard) for the
   campaign-write path in Phase 1.
