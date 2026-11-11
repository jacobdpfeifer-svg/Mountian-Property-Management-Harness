# Q6 — Multi-tenant readiness

**Verdict: CHANGE, using one install per tenant. Do not retrofit `tenant_id`.** This is a
single-operator CLI on one SQLite file, with Mont Luxe file paths, a Grand County market
default, and no user identity. A 50-home manager could not share this install tomorrow,
and should not. `docs/ARCHITECTURE.md:57` already lists "SaaS multi-tenant" as out of
scope. The cheapest honest route is a configurable config root plus a separate DB per
operator. Then fix what breaks at 50 homes even with a single tenant: market and timezone
defaults, crew modelling, alias collisions, no auth, and CLI output volume.

## What breaks, with evidence

Effort scale: S ≤ 1 day, M ≤ 1 week, L > 1 week.

### A. Configuration is Mont Luxe-shaped

| # | Break | Evidence | Fix | Effort |
|---|---|---|---|---|
| A1 | Config paths are constants with no override | `src/config.py:51` `PORTFOLIO_PATH = …/mont_luxe.yaml`; `src/ops/profiles.py:20-21` `OPS_CONFIG_PATH`, `OPS_POLICY_PATH`; `src/compliance/__init__.py:29` `RULE_PACK_DIR` | Add a `WP_PRICE_CONFIG_ROOT` env var resolved in one place | S |
| A2 | Hard-coded Mont Luxe owner map is still used as a fallback | `src/db/__init__.py:13-17` `PROPERTY_OWNER_IDS`, used by `locked_portfolio_property_ids` (`:297-313`) when the portfolio YAML fails to load, and by the ledger import (`src/ops/sources/csv_import.py:272`) | Delete it; fail closed | S |
| A3 | A home with no ops profile silently gets no ops effect | `src/ops/pricing_hook.py:105-107` returns `None`; `src/ops/incidents.py:81` and `src/ops/cli.py:180` intersect profiles with the portfolio | Coverage check in `ops profiles`: every portfolio home has a profile, or it fails | S |
| A4 | One YAML file for 50 homes is workable but fragile. Every save re-versions only the changed homes (good, `profiles.py:34-36`), but defaults are global, with no per-building or per-zone tier | `config/operations/mont_luxe.yaml:14-26` | Allow `defaults_by_zone`; keep one file | S |
| A5 | Duplicate aliases silently resolve to the last home listed, contradicting "Never guesses" | `src/ops/sources/__init__.py:34`, `:42-44` (`self._lookup[name] = pid` overwrites) | Reject duplicate aliases at load | S |
| A6 | Error messages and branding name Mont Luxe | `src/receipt/owner_monthly.py:303` (`<title>Mont Luxe owner receipt`), `:125`; `src/compliance/__init__.py:266`; `src/ops/shadow.py:174` | Take the tenant name from the `tenants` row | S |

### B. Market and jurisdiction

| # | Break | Evidence | Fix | Effort |
|---|---|---|---|---|
| B1 | A property with no `market_id` silently gets Grand County weather and CDOT signals | `src/ops/turns.py:118-125` returns `"grand_home"` as the fallback | Raise instead | S |
| B2 | Turn windows always use America/Denver, even though the portfolio has a `timezone` key | `src/ops/turns.py:189` default; `derive_turns` never passes it (`:250-259`). Compare `src/ops/actions.py:203`, which does read the portfolio timezone | Pass the timezone of the property or tenant | S |
| B3 | Signal collection is hard-wired to Colorado markets | `src/signals/orchestrator.py:13-21` (`cdot`, `resort`, `weather` → `grand_home`) | Read the market list from config | M |
| B4 | One global ops policy carries Colorado-specific rules: Berthoud and chain-law buffers, `auto_at_risk`, incident rules, and guest-notice text naming US-40, Winter Park, and cotrip.org | `config/policies/operations.yaml:25-32`, `:79-88`, `:100-112`, `:143-159` | Split into `operations.yaml` (generic) plus `markets/<id>/operations.yaml` | M |
| B5 | Jurisdiction packs are per-file and fail closed when one is missing (good, `compliance/__init__.py:77-80`). But each new market needs a researched, human-reviewed pack | `config/compliance/` has 3 packs, all Grand County. Packs carry `reviewed_by: null` until reviewed | Research plus review per jurisdiction: code S, content M per market | S + M/market |

### C. Crews

| # | Break | Evidence | Fix | Effort |
|---|---|---|---|---|
| C1 | A crew that serves N zones is counted N times | `src/ops/economics.py:184-193`; persisted by `src/ops/sources/manual.py:17-28` | Crew-day scheduling (see Q2) | M |
| C2 | There is no crew identity on a turn, so you can't ask "which team is overloaded" | `Turn` dataclass (`src/ops/turns.py:38-53`); `assignee_ref` is imported (`schema.sql:76`) but never used | Carry the assignee or crew on each turn | S (after C1) |
| C3 | Snow and hot-tub vendors are modelled as cleaner minutes | `src/ops/__init__.py:43-52` | Give service types their own capacity pools; `service_type` already exists in the snapshot PK (`schema.sql:52`, `:59`) | M |

### D. Owner data separation

`load_owner_month` scopes correctly. It reads owner→properties from config
(`owner_monthly.py:118-136`), filters every query to those properties, and filters
incidents by property overlap (`:225-233`). The problems are at the edges:

| # | Break | Evidence | Fix | Effort |
|---|---|---|---|---|
| D1 | **Ledger rows with a typo'd property become owner-level charges.** If the property doesn't resolve, `pid` is `None`. When `owner_id` is present, the row is accepted as an owner-level entry (`property_id IS NULL`) and shows up on that owner's receipt (`owner_monthly.py:197-204`) | `src/ops/sources/csv_import.py:271-286` | Reject when `property` is set but doesn't resolve | S |
| D2 | **Ledger rows whose owner doesn't match the property's owner vanish from both receipts.** Nothing cross-checks `owner_id` against the portfolio's `owner_id` for that property, and both receipts filter on the pair | `csv_import.py:272`; `owner_monthly.py:190-195` | Validate against portfolio ownership | S |
| D3 | Receipts are written to `<memory root>/receipts/owner/{owner_id}_{month}.html`. Owner ids are short slugs (`northwoods`, `cloud9`), so two tenants on one machine would overwrite each other | `owner_monthly.py:369-370`; ops drafts all go to a single `…/ops` dir (`src/ops/actions.py:62-69`) | Moot with one install per tenant. Otherwise prefix with the tenant | S |
| D4 | Owners with shared or changing ownership: owner→property mapping is current config only, so a mid-month sale re-attributes the whole month | `owner_monthly.py:132` | Effective-dated ownership | M |

### E. Access control and tenancy in the database

| # | Break | Evidence | Fix | Effort |
|---|---|---|---|---|
| E1 | **No authentication at all.** Every actor is a free-text CLI argument, including the "named human" who verifies readiness and approves incident actions | `src/ops/cli.py:298`, `:323`, `:330`, `:335`; `readiness.py:226-228` only rejects the literal strings operator/human/user/unknown | User identity plus roles (viewer, field, ops lead, owner-read). Prerequisite for any phone flow (Q4) | L |
| E2 | One SQLite file, opened by whoever has shell access | `src/db/__init__.py:10` `DEFAULT_DB_PATH = …/data/wp_pricing.db` | With one install per tenant this is fine for 50 homes and a few users through an API. Concurrent phone writers need WAL plus a single API process, or Postgres | M |
| E3 | `tenant_id` exists only on `tenants` and `properties` (`src/db/schema.sql:6-31`). No ops table has it (`src/ops/schema.sql`, entire file). `properties.property_id` is a global PK (`schema.sql:31`) | — | Don't add it. Isolate per install | — (or L) |
| E4 | Incident ids hash `type|market|start` (`src/ops/incidents.py:45-47`). Two tenants in the same market would share an incident, and the second scan overwrites `affected_json` (`:124-129`) | — | Moot with one install per tenant | — |

### F. Performance (from reading the code; not measured)

At 50 homes × 365 nights, a full recommend run makes on the order of **0.5–1 M SQLite
queries**. That's seconds to tens of seconds: fine for a nightly batch, not a blocker.

| # | Hot spot | Evidence | Fix | Effort |
|---|---|---|---|---|
| F1 | `state_for_night` loads a property's **entire** transition history for every night | `src/ops/readiness.py:131-135` | Memoize per (property, as_of) | S |
| F2 | The pricing hook runs 2 gap queries per night. Then, per candidate length, it builds 2 turns × 5 un-memoized signal reads, plus `market_for` | `src/ops/pricing_hook.py:113-129`; `turns.py:157-176` | Memoize `weather_buffer` per (market, date, as_of) | S |
| F3 | `observed_readiness` re-derives 730 days of turns for every home (5 signal reads per turn). It is memoized per run | `economics.py:138-148`; `pricing_hook.py:109` | Same memo as F2 | S |
| F4 | The shadow capacity loop is O(days × zones × all turns) | `src/ops/shadow.py:157-172`; `economics.py:222-223` | Group turns by (date, zone) once | S |

### G. CLI ergonomics at 50 homes

- `ops report` prints one line per turn (`shadow.py:236-245`). For 50 homes over 90 days
  that is ~1,000 lines. `ops capacity` prints every turn regardless of zone
  (`cli.py:132-134`).
- Readiness changes go one home at a time through `event add --property … --actor …`
  (`cli.py:282-301`). Incidents are approved one action at a time (`cli.py:320-326`).
- `ops readiness` labels each home with the latest row rather than tonight's state
  (`cli.py:186`; see Q4 B3).
- **Fix:** add `--zone`, `--only-flagged`, and `--property` everywhere, plus a one-page
  "today" summary. **M.**
- The real answer at 50 homes is the phone/API surface from Q4, which depends on E1.

## Proposal and order

1. **One install per tenant** (A1, A2, B1, B2, A5, D1, D2, F1–F4): ≈ **2–3 days**. After
   this, a second operator can run a separate checkout with its own config root and DB
   without inheriting Mont Luxe defaults or bad ledger rows.
2. **Market-specific policy and signals** (B3, B4, plus each new jurisdiction pack in B5):
   **M per new market**, mostly research.
3. **Crew model** (C1–C3), shared with Q2: **M**.
4. **Identity, roles, and an API for the phone flow** (E1, E2, G): **L**. Until this
   exists, "named human" is an honour system, and staff need shell access to the single
   machine.

Shared-database multi-tenancy (E3, E4, `tenant_id` on every row, row-level filters, and
an isolation test suite) is **L+**. It buys nothing at 1–5 operators that separate
installs don't already provide.

## Sources

No outside sources. All findings come from reading the `audit/ops-compliance` worktree on
2026-10-06. The performance figures are estimates from counting queries in the code, not
measurements. D1 and D2 come from reading `_import_ledger` and were not executed.
