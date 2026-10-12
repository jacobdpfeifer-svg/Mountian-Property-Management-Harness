# Operations and compliance inventory

Audit target: `origin/feature/ops-layer-wip` at `56a2ffb`, audited from the isolated
`audit/ops-compliance` worktree. The iCloud checkout was not used as a source.

## Entry points

| Command | Reads | Writes | Network |
|---|---|---|---|
| `ops sources` | config, import-run history | none; SQLite query-only | no |
| `ops profiles` | operations YAML | profile versions in operator DB | no |
| `ops import --source manual` | operations YAML, dates | profiles and capacity snapshots | no |
| `ops import --source csv` | CSV, operations aliases | outcomes, capacity, events, ledger, credentials | no |
| `ops import --source telemetry` | telemetry JSON | asset events and readiness risk | no |
| `ops import --source webhooks` | recorded PMS webhook rows | normalized outcomes | no |
| `ops import --source guesty_tasks` | Guesty Tasks API | normalized outcomes and import run | yes, read-only |
| `ops import --source breezeway` | Breezeway API | normalized outcomes and import run | yes, read-only |
| `ops import --source turno` | Turno API | normalized outcomes and import run | yes, read-only |
| `ops report` | operator DB copy, profiles, policy | none; query-only | no |
| `ops capacity` | operator DB copy, profiles, roster | none; query-only | no |
| `ops event add` | event input, evidence row | asset event and optional readiness transition | no |
| `ops readiness` | events, signals, reservations | signal scan may add event/transition rows | no |
| `ops incidents scan` | signals, profiles, reservations | incident candidates | no |
| `ops incidents approve` | incident row, policy | action log and private drafts; live task write only behind explicit gate | optional |
| `ops incidents reject/outcome` | incident row | action log and optional close | no |
| `compliance add` | credential and evidence file | credential row | no |
| `compliance import` | CSV | credential rows | no |
| `compliance check` | portfolio, rule packs, credentials, optional listing text | none; query-only | no |
| `owner-receipt` | owner-scoped DB rows and compliance register | private HTML receipt | no |

The audit branch adds an explicit locked-portfolio default to unscoped ops report,
capacity, readiness, and incident scans. Property resolution also refuses a database
property that is not declared in the portfolio.

## Tables and point-in-time behavior

| Table | Writers | Readers | Point-in-time filter |
|---|---|---|---|
| `property_operations_profile` | profile loader | economics, shadow, pricing hook | `loaded_at <= as_of`; current YAML fallback disclosed |
| `ops_import_runs` | all imports | source status/reporting | status history; no decision use |
| `operations_capacity_snapshots` | manual/CSV/API imports | capacity economics | `as_of <= decision as_of` |
| `turnover_outcomes` | outcome imports/webhooks | cost, readiness probability, shadow | service date and import timestamp bounded |
| `asset_health_events` | event/telemetry/signal/action paths | readiness, incidents, receipt | event timestamps and system-specific state history |
| `readiness_transitions` | readiness state machine | compose, CLI, receipt | `at <= as_of`; night window checked separately |
| `incidents` | incident scan | incident CLI/actions/receipt | signal observations bounded by scan `as_of`; incident list is current |
| `incident_actions` | approve/reject/outcome | incident show/receipt | append-only log; no decision replay filter |
| `incident_task_writes` | gated live task writer | retry/reconciliation path | current write intent/status |
| `property_credentials` | compliance add/import | compliance checker/receipt | credential deadline evaluated at `as_of`; evidence hash checked |
| `owner_ledger_entries` | ledger import | owner receipt | month bounds and owner/property scope |

## Configuration contract

`config/policies/operations.yaml` keys actually consumed include `economics`,
`slack.weather_buffers`, `ready_probability`, `capacity`, `stay`, `readiness`,
`telemetry`, `incidents`, and `guest_notice_templates`. The three rule packs consume
`jurisdiction`, `version`, `source_urls`, `reviewed_by`, `requirements`, and optional
`max_occupancy`/`notes`. The operations profile consumes defaults, per-property
profile fields, aliases, and capacity roster/overrides.

Known unused or weakly enforced configuration:

- `config/policies/operations.yaml:capacity.warn_utilization` and
  `critical_utilization` are report labels, not gates in compose.
- Rule-pack `source_urls` are disclosed but are not fetched or compared by the checker.
- Compliance `count` is enforced, but there is no reservation night-cap or guest-count
  cross-check.
- `operations.readiness_gate` is enforced only when an event-derived state exists;
  no-event properties intentionally behave as pricing-with-ops-disabled.

## Consumer map

| Output | Consumer | Effect |
|---|---|---|
| turn slack / P(ready) | `pricing_hook`, shadow report | optional longer min-stay suggestion; no price decrease |
| turn cost | compose explanation and stay model | explanation/risk objective only; stay model is off |
| readiness state | compose | suggest-only, blocks upward move, or blocks night; never writes inventory |
| incident candidate | CLI/actions/receipt | drafts, lists, task suggestions, or human review |
| compliance result | CLI/owner receipt | evidence/deadline disclosure only |
| profile version | shadow report/pricing hook | historical reproducibility and estimate disclosure |
| task/telemetry outcomes | economics/readiness | observed cost, readiness evidence, or risk |
| recommended min-stay | push boundary | policy/inventory values may pass; ops-sourced values are dropped |

## Tooling baseline

On Python 3.12.14:

- Full suite excluding `* 2.py`: **456 passed, 1 skipped, 2 deselected**.
- Ops/compliance lane with audit tests: **80 passed**.
- Branch coverage for `src/ops` and `src/compliance`: **70.21%**, just above the
  project 70% threshold. The weakest files are `ops/shadow.py` 61%,
  `sources/breezeway.py` 57%, `sources/turno.py` 69%, `sources/guesty_tasks.py` 68%,
  and `ops/cli.py`/`compliance/cli.py` at 0%.
- `mypy src/ops src/compliance`: passes with no issues.
- `ruff check src/ops src/compliance`: 29 findings, including timezone-naive datetime
  construction, broad exception catches in API import, and import/style findings.

