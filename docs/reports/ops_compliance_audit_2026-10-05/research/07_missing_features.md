# Q7 — What's missing, ranked by buyer value vs build cost

Desk research and code grep, 2026-10-06, on branch `audit/ops-compliance`
(`~/wp-price-worktrees/ops-audit`). "Expected" means at least one vendor page opened in
Q1 states the feature, or the 2026-09-30 operator research sample asks for it. Vendor
claims are **vendor states**, not tested. Build cost is a rough estimate for this
codebase (S ≈ days, M ≈ 1 to 3 weeks, L ≈ a month or more, or a new surface such as a
mobile app), and assumes one engineer.

## Verdict

Most of what buyers expect from "operations software" is missing, and **most of it should
stay missing**. Checklists with photos, linen/consumable inventory, damage claims, payroll
and smart-lock control are what Breezeway, Operto, Guesty Tasks and Streamline already
state they sell. Building them would turn this repo into a weaker copy of those products,
which the research sample explicitly warns against. The gaps that matter are the ones that
stop **our own differentiator** (ops → pricing bridge, readiness gate, owner proof) from
working on real data:
1. no verified live task feed and no stale-feed alarm,
2. turn records too thin to calibrate P(ready) (no accepted/started/inspected timestamps
   or exception codes),
3. no way to tell a person an exception exists (no notifications),
4. owner-facing readiness history without evidence attached,
5. ops tables with no tenant scoping and rule packs only for three Grand County
   jurisdictions, all unreviewed.

**Verdicts:** readiness state machine: **keep** (add evidence links, don't add turn-progress
states; import those). Importers: **keep, but change**: widen the fields read
(checklist completion, photo refs, accepted/started/inspected) and add staleness checks.
Compliance register: **keep**, but add Summit/Eagle/Routt packs only with a named
reviewer. Owner receipt: **change**: add a readiness/evidence block. Don't build field
tools; **replace** that ambition with imports.

## Absence verification (grep over `src/ops`, `src/compliance`, `src/receipt`, `config/operations`, `config/compliance`, `config/policies/operations.yaml`)

| Term(s) | Hits | Reading |
|---|---|---|
| `photo`, `image` | none | No photo evidence anywhere |
| `checklist` | `config/compliance/grand_county_unincorporated.yaml` only | Rule-pack wording; no checklist model |
| `sla` | only inside `slack` (turns, economics, shadow, pricing_hook, policy) | No vendor SLA |
| `damage` | none; `claim` only in `src/receipt/render.py` (receipt wording) | No damage claims |
| `inventory` | pricing_hook, shadow, readiness, actions, breezeway, policy | All mean **booking inventory/closures**, not supplies |
| `linen`, `consumable`, `supplies` | `normalize.py` (classifies a task as laundry), profile cost lines, ledger `category='supplies'` | Flat per-turn cost estimates (`fixed_cost_per_turn: 60`, `laundry_cost_per_turn: 180`); no stock levels |
| `restock` | none | |
| `portal` | none | Owner sees only the monthly HTML receipt |
| `history` | none | Receipt lists the month's `readiness_transitions` (`owner_monthly.py` L241–294) with no evidence or cross-month view |
| `work_order` | none | |
| `preventive`, `recurring` | ledger category `preventive` only (`src/ops/schema.sql` L197) | No preventive-maintenance schedule |
| `noise` | none | Telemetry is generic; no noise/occupancy device handling |
| `payroll`, `timesheet` | none | |
| `notify`, `sms`, `email` | none | No alerting channel of any kind |
| `tenant` | ops: comments only; `src/db/schema.sql` has a `tenants` table with default `mont_luxe_collection` | Ops/compliance tables carry no `tenant_id` |
| `accepted_at`, `started_at`, `inspected_at` | `started_at` only on import runs (`schema.sql` L38) | `turnover_outcomes` has `scheduled_start, completed_at, qa_pass, rework_minutes, late_ready_minutes` and no exception code |
| `stale`, `max_age` in `src/ops/sources/__init__.py` | none | `ops sources` shows `last_run`, but nothing flags an old feed |

## Ranked list

Ranking = buyer value first, then lower cost. "Build/Import" says whether to build it or
read it from a vendor.

| # | Feature | Buyer value | Build cost | Build or import | One-line reasoning |
|---:|---|---|---|---|---|
| 1 | **Verified live task feed + stale-feed alarm** (one of Guesty Tasks / Breezeway proven on a real tenant; warn when last import is older than N hours and fall back to "no ops input") | High | M | Build (connector), data via import | Without it P(ready) and turn cost run on `basis: estimate` profiles; a silent stale feed would make the readiness gate lie |
| 2 | **Richer turn record**: `accepted_at, started_at, inspected_at, exception_code, verified_by` on `turnover_outcomes` | High | S | Build schema + map from vendor fields | The research sample's minimum data contract; vendors state they timestamp checklist steps (Guesty) so the data likely exists |
| 3 | **Exception notifications** (email/SMS/Slack for new incident, readiness change, expiring credential) | High | S–M | Build (thin), or create a Guesty task as the notification | An exception queue nobody is pinged about doesn't change outcomes; every vendor ships alerts |
| 4 | **Owner-facing readiness history with evidence** (per-property timeline: event, who verified, sensor reading, link to vendor photo) | High | S | Build on existing `readiness_transitions` + `asset_health_events` | Receipt already lists transitions; adding evidence refs and a 12-month view is cheap and is the "proof" owners ask for. Guesty's portal states it shows task photos, so ours must at least link them |
| 5 | **Inspection checklist + photo evidence** | High | L to build, S–M to import refs | **Import** (Breezeway "task requirements" / property photos API; Guesty checklist and photo uploads) | Every ops vendor states it does this; a mobile capture app is a new product surface. Store only completion % and photo URLs as evidence for `verified_ready` |
| 6 | **Compliance rule packs for target counties** (Summit, Eagle, Routt, Pitkin, San Miguel, Gunnison, plus towns) with named reviewer | High for target buyers | M per batch (legal review is the cost, not code) | Build | Only `fraser`, `winter_park`, `grand_county_unincorporated` exist, all `reviewed_by: null`; most sample targets are outside Grand County |
| 7 | **Tenant scoping on ops and compliance tables + roles** | High once >1 customer | L | Build | `tenants` table exists in core schema but ops tables have no `tenant_id`; no roles or auth since there is no UI |
| 8 | **A non-CLI interface** (web exception queue; approve/reject incident actions) | High | L | Build | Approve/reject is `wp-price ops incidents approve … --actor`; a housekeeping manager will not use a CLI |
| 9 | **Vendor SLAs** (per-vendor expected accept/complete times; breach → `at_risk` + notify) | Medium–High | M | Build on top of #2 | Needs #2's timestamps first; turns missed SLAs into the readiness signal we already consume |
| 10 | **Non-Guesty PMS connectors** (Hostaway, Track, Streamline) | Medium–High (market reach) | M each | Build | Sample #2 (Visit Winter Park Lodging) is on Streamline; today any non-Guesty shop is excluded |
| 11 | **Preventive / recurring maintenance schedule** (hot tub, furnace, fireplace, CO detectors) | Medium | M | Import (Guesty recurring tasks, Breezeway, Operto state it) | Only overlap that matters to us: a lapsed fireplace cleaning is already a compliance item; read due dates rather than schedule them |
| 12 | **Noise / occupancy device signals** (Minut, NoiseAware) into telemetry | Medium | S | Import via existing `telemetry` JSON | Can only set `at_risk` by doctrine; useful for occupancy-limit compliance evidence |
| 13 | **Lodging-tax filing status** as compliance evidence (e.g. MyLodgeTax filed/remitted) | Medium | S | Import evidence; never file | Filing and remittance are money movement; doctrine forbids it and Avalara states it does it |
| 14 | **Work orders with owner-approval thresholds** | Medium | M | Import (Guesty/Streamline state work orders) | Owner approval of spend is a PMS/accounting flow; we would only display it on the receipt |
| 15 | **Linen and consumable inventory** | Medium | L | **Don't build**; import supply cost if needed | Breezeway and Operto state stock thresholds and auto-deduction; ours has a flat $60 + $180 per turn estimate, which is enough for turn cost |
| 16 | **Damage claims and evidence chain** | Medium | L | **Don't build** | Requires before/after photos (#5), guest communication and money movement (all out of doctrine); Operto states "bill owners … with time stamped proof" |
| 17 | **Payroll / time tracking** | Low for us | L | Don't build | Operto states it; irrelevant to the pricing bridge |
| 18 | **Trust-account reconciliation** | High for buyers, but regulated | L | Don't build (already out of scope in OPERATIONS.md) | Track and Streamline state native trust accounting; we lack accounting access and licensed review |

## What the ranking implies

- Items 1 to 4 are the cheapest path to making the existing ops layer **true on real
  data**; together they're roughly M + S + S–M + S. Nothing else should start before #1.
- Items 5, 9, 11 and 14 become cheap only if we **import** from the buyer's task tool.
  Building them natively is the "second generic operations platform" the sample says not
  to build.
- Items 7 and 8 gate selling to anyone except the current operator. They are the largest
  costs and the least differentiated, and are where ours is weakest against every vendor.
- Items 15 to 18: decline, and say so on the sales sheet rather than implying parity.

## Sources

Opened 2026-10-06. Full list of vendor URLs and load status is in
`01_buyer_workflows.md`; the ones that support claims in this file:

| URL | Status | Used for |
|---|---|---|
| https://www.breezeway.io/ | loaded | checklists, photo uploads, auto-assign, supplies |
| https://www.breezeway.io/inventory | loaded | low-stock thresholds, auto-deduction (no damage/photo content on page) |
| https://developer.breezeway.io/ | loaded | task requirements, supplies, property photos, webhooks in API |
| https://www.guesty.com/features/tasks-management/ | loaded | reservation-triggered and recurring tasks, checklists, photos, work orders |
| https://www.guesty.com/features/homeowners-portal/ | loaded | owners see cleaning/inspection photos |
| https://operto.com/teams/ | loaded | checklists, photo/video proof, inventory, linen, payroll, owner billing with proof |
| https://operto.com/ | loaded | noise and thermostat integrations |
| https://www.streamlinevrs.com/ | loaded | work orders, POS inventory, trust accounting |
| https://www.streamlinevrs.com/features/ | loaded | Property Care app with photo QC |
| https://trackhospitality.com/track-pms/ | loaded | trust accounting, housekeeping/maintenance |
| https://www.avalara.com/mylodgetax/en/index.html | loaded | registration, filing, remittance |
| https://turno.com/ | failed (403) | Turno capabilities unverified |
| https://www.hostaway.com/features/task-management/ | failed (404) | Hostaway task detail unverified |
| https://www.breezeway.io/property-care | failed (404) | |
| local: `MOUNTAIN_OPERATOR_RESEARCH_SAMPLE_2026-09-30.md` | read | data contract, readiness states, owner proof block |
| local: `src/ops/schema.sql`, `src/db/schema.sql`, `src/ops/**`, `src/compliance/**`, `src/receipt/owner_monthly.py`, `config/operations/mont_luxe.yaml`, `config/compliance/*.yaml` | read/grepped | absence verification |
