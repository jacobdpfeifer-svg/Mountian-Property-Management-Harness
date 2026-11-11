# Operations and compliance inventory

Audit target: `origin/feature/ops-layer-wip` at `56a2ffb`, audited on branch
`audit/ops-compliance` in `~/wp-price-worktrees/ops-audit` (outside iCloud). The iCloud
checkout's stale untracked copies of `src/ops` and `src/compliance` were not used.
First pass 2026-10-05; completed 2026-10-06. Numbers below are as of the final audit
commit unless marked "before".

## Entry points

All commands are `PYTHONPATH=. .venv/bin/python -m src.cli.main [--db PATH] <command>`.
"Opens" says how the database is opened: `rw` is `src.db.connect`, which also applies
schema patches on open (a write even when the command itself writes nothing).

| Command | Reads | Writes | Opens | Network |
|---|---|---|---|---|
| `ops sources` | import-run history | nothing | read-only | no |
| `ops profiles` | `config/operations/mont_luxe.yaml` | new profile versions | rw | no |
| `ops import --source manual` | roster, dates | capacity snapshots | rw | no |
| `ops import --source csv --kind outcomes\|capacity\|asset_events\|ledger\|credentials` | CSV, aliases | that table + `ops_import_runs` | rw | no |
| `ops import --source telemetry` | sensor JSON | asset events; at_risk on a critical reading | rw | no |
| `ops import --source webhooks` | stored PMS webhook rows | turnover outcomes | rw | no |
| `ops import --source guesty_tasks\|breezeway\|turno` | vendor API (GET only) | outcomes, import run | rw | yes, read-only |
| `ops report` | reservations, inventory, ops tables, profiles | nothing | read-only (TEMP ops tables if absent, audit fix OPS-012) | no |
| `ops capacity` | turns, roster, snapshots | nothing | rw | no |
| `ops event add` | flags | asset event, optional transition (event committed even if the transition is refused, OPS-030) | rw | no |
| `ops readiness [--scan-signals]` | transitions, signals | with `--scan-signals`: events and at_risk rows | rw | no |
| `ops incidents scan\|list\|show` | signals, reservations | scan: incident rows | rw | no |
| `ops incidents approve` | incident, policy | action log, private drafts; Guesty task only with `--confirm-live-write` on a production DB | rw | only when gated |
| `ops incidents reject\|outcome` | incident | action log | rw | no |
| `compliance add\|import` | credential, evidence file | credential rows | rw | no |
| `compliance check` | portfolio, packs, credentials, reservations | nothing | read-only (TEMP tables if absent) | no |
| `owner-receipt` | owner-scoped rows, register | private HTML under `~/Library/Application Support/MontLuxePricing/receipts/owner` | read-only | no |

Unscoped `ops report`, `ops capacity`, `ops readiness`, and `ops incidents scan` use the
locked portfolio (`config/portfolio/mont_luxe.yaml`) since audit commit `3d7d3ef`; the
property resolver refuses a database home that is not declared (`creekside_haven` is in
the operator DB).

## Tables and point-in-time behavior

| Table | Writers | Readers | Point-in-time filter |
|---|---|---|---|
| `property_operations_profile` | `ops profiles`, sim | economics, shadow, pricing hook | `loaded_at <= as_of`; current YAML fallback is disclosed |
| `ops_import_runs` | every import | `ops sources` only (display) | none; no decision reads it (stale feeds are invisible, OPS-006) |
| `operations_capacity_snapshots` | manual, CSV, Breezeway | capacity view | `as_of <= decision as_of` |
| `turnover_outcomes` | CSV, webhooks, vendor APIs | turn cost, P(ready), shadow | `service_date < as_of` and import date `<= as_of` (same-day import counts, P3) |
| `asset_health_events` | telemetry, CSV, `ops event`, signal scan, `suppress_auto_price` | readiness, receipt | stored as local wall clock since OPS-015 |
| `readiness_transitions` | readiness state machine | compose, CLI, receipt, shadow | `at <= as_of`; per-night state via `state_for_night` |
| `incidents` / `incident_actions` / `incident_task_writes` | scan / approve / gated writer | CLI, receipt | scan reads signals point-in-time; the incident list is current state |
| `property_credentials` | `compliance add/import`, CSV | checker, receipt | deadlines evaluated at `as_of` |
| `owner_ledger_entries` | CSV ledger import | owner receipt | month bounds; owner and property must match since OPS-023 |
| `reservations` (core) | Guesty sync | turns, incidents, booked-occupancy check | status is current (a later cancellation removes a stay from a historical replay, P3); confirmation date filters arrivals |

## Configuration contract

Every key in `config/operations/mont_luxe.yaml` and `config/policies/operations.yaml` has a
reader in `src` (checked mechanically; `readiness.sensor_verification.*.min_temp_f` is read
by prefix as a minimum on reading key `temp_f`). Keys that are read but weakly enforced:

- `capacity.warn_utilization` / `critical_utilization` label rows in the shadow report only;
  nothing in compose or P(ready) reads capacity.
- `telemetry.spa` has only `warn_below_f`; a spa reading can never derive `critical`, so a
  dead hot tub reported without an explicit severity never sets at_risk (OPS-031).
- `readiness.sensor_verification.heat.min_temp_f: 50` lets a heat sensor verify a house as
  guest-ready at 50°F (P3).
- Rule packs: `source_urls` are disclosed; per-entry `source` and `review` are now required
  by the loader. No pack has `reviewed_by`.
- `operations.readiness_gate` (default policy) is on; with no events it is inert, proven
  byte-identical to the gate off across the 336-cell matrix.
- `models.ops_aware_stay` is off; its only output is an unpushed min-stay suggestion.

## Consumers

| Output | Consumer | Effect on price / autonomy / inventory |
|---|---|---|
| readiness state (per night) | compose | at_risk and inspection_required demote handle → suggest; inspection_required holds at max(listed, floor), escalating on conflict; out_of_service and remediation block and escalate. Never raises a price, never grants autonomy, never writes inventory. |
| readiness reason | explanation | pinned first with its dollar effect (OPS-028 fix) |
| turn cost, P(ready) | `ops_aware_stay` (off), shadow report | a longer *suggested* min-stay, source `ops` |
| ops min-stay | push | dropped at the write boundary (`src/pms/__init__.py`) |
| capacity view | shadow report | labels only |
| incident candidates | CLI, actions, receipt | drafts, lists, gated task creation; forbidden actions raise |
| compliance results | CLI, owner receipt | disclosure only; never pricing |
| `ops_import_runs` | `ops sources` | display only |
| owner ledger | owner receipt | owner-scoped charges |

## Tooling

Python 3.12.14, venv rebuilt for this pass (the worktree venv was a bare 3.9).

| Measure | Before (2026-10-05) | After |
|---|---|---|
| Full suite (`--ignore-glob="* 2.py"`) | 456 passed, 1 skipped, 2 deselected | see REPORT.md |
| Ops lane `tests/ops` | 80 | 438 (336 matrix cells, 7 push-seam cells, Hypothesis property test) |
| Branch coverage `src/ops` + `src/compliance` | 70.21% | 78% |
| `mypy src/ops src/compliance` | clean | clean |
| `ruff check src/ops src/compliance` | 29 | 35; the increase is cosmetic (import sorting, `re.S` alias, implicit concatenation). Naive-datetime findings remain in CLI defaults. |

Weakest coverage: `src/ops/cli.py` 39%, `src/compliance/cli.py` 46%, `sources/breezeway.py`
57%, `sources/guesty_tasks.py` 68%, `sources/turno.py` 69%, `actions.py` 69%. The vendor
adapters' low coverage matters most: `research/08_adapter_field_check.md` shows the Turno
adapter cannot parse its own vendor's documented response.
