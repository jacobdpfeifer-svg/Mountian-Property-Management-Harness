# Operations layer — doctrine and runbook

**Question it answers:** can we profitably and reliably service the stay this
price is likely to create?

Guesty stays the system of record. This layer reads reservations, task
outcomes, crew capacity, sensor readings and signals. It hands pricing a small
set of conservative inputs and writes drafts and suggestions for a person to act on.

## What operations may and may not do

| Operations may | Operations may never |
|---|---|
| Suggest a **longer** minimum stay (source `ops`) | Lower a price because feasibility is low |
| Block upward price moves for a night under inspection | Push an ops-sourced min-stay to Guesty (`push` drops it) |
| Demote a night to `suggest` (at_risk / inspection) | Write availability or close inventory |
| Block a night and **recommend** a closure (out_of_service) | Cancel or move reservations, promise refunds, pay vendors |
| Draft guest notices from approved factual templates | Send guest messages or access codes |
| Create a Guesty task, only with `--confirm-live-write` on a production DB | Make safety determinations |

Forbidden incident actions raise `ForbiddenAction` in code (`src/ops/actions.py`).
A rule in `config/policies/operations.yaml` that lists one fails the scan.

## Pieces

- **Profiles** (`config/operations/mont_luxe.yaml`): per-home turnover minutes,
  crew size, rates, access zone, crew roster and aliases. Every value is
  `basis: estimate` until the operator confirms it. A profile's version is the
  hash of its content.
- **Turns** (`src/ops/turns.py`): the unit of work is a stay transition,
  `turn_id = property|departing|arriving`, serviced on the checkout date. Owner
  stays need turns too.
- **Economics** (`src/ops/economics.py`):
  - **Turn cost:** the median of imported costs once a home has 5 or more observed turns; before that, the profile build-up.
  - **Turn slack:** check-in minus checkout, less elapsed work, travel, and a weather buffer read point-in-time from `signal_observations`.
  - **P(ready on time):** a Beta-shrunk on-time rate per slack bucket.
  - **Capacity utilization:** committed over available worker-minutes per zone and date.
- **Shadow report** (`wp-price ops report`): turns, costs, readiness, capacity
  pressure, and the worst-case number of extra turns each min-stay setting
  allows. It writes nothing.
- **Ops-aware stay length** (`models.ops_aware_stay`, **off**):
  - Each candidate stay is charged one turn plus (1 − P(ready)) × risk premium.
  - Candidates below `min_p_ready` are escalated.
  - A longer stay is suggested only when the per-night gain is at least `min_gain_pct` of the anchor price.
  - **Known limitation:** the comparison assumes every candidate stay sells. It cannot see the demand a longer minimum loses. That is why it stays suggestion-only and never pushes.
- **Readiness** (`src/ops/readiness.py`):
  - States: `ready → at_risk → inspection_required → out_of_service → remediation_in_progress → verified_ready → ready`.
  - Every transition cites an asset event.
  - Signals and telemetry may only set `at_risk`.
  - `verified_ready` needs a named person, or a sensor reading that passes `readiness.sensor_verification`.
  - The compose gate (`operations.readiness_gate`, on) has no effect until an event is recorded.
- **Incidents** (`src/ops/incidents.py`):
  - A threshold crossed on a signal becomes an idempotent incident, with the affected arrivals, departures and turns.
  - A person approves each action; every step is logged in `incident_actions`.
  - Outputs go to private operator storage (`~/Library/Application Support/MontLuxePricing/ops`), never the repo or iCloud.
- **Compliance** (`src/compliance`, `config/compliance/*.yaml`):
  - Tracks documents and deadlines. Statuses are `evidence_on_file | unverified | expiring | expired | missing`, never "compliant".
  - Rule packs carry source URLs and `reviewed_by: null` until a person reviews them. Every check warns while a pack is unreviewed.
- **Owner receipt** (`wp-price owner-receipt`): net performance (revenue, channel
  cost derived from Guesty payouts, invoiced vs estimated service, ledger,
  management fee), revenue decisions, property care, exceptions. It refuses
  placeholder owner names unless `--allow-placeholder-names` is passed.
  **Trust-account reconciliation is out of scope** until accounting access and
  licensed-professional review exist.

## Data paths

All of them write through `src/ops/db.py`. Outcomes are idempotent on `(source, source_task_id)`.

| Source | Command | Status |
|---|---|---|
| Profiles + roster | `wp-price ops import --source manual --from … --to …` | works; values are estimates |
| CSV (outcomes, capacity, asset_events, ledger, credentials) | `wp-price ops import --source csv --file F --kind K [--preset P]` | works; templates in `data/sample/ops/` |
| CSV presets `turno`, `breezeway_export`, `guesty_tasks_export` | `--preset …` | header mappings are best guesses; check against a real export |
| Guesty Tasks API | `--source guesty_tasks` | `GET /v1/tasks-open-api/tasks` per the public reference; not yet verified on the tenant. Supplies duration and lateness, not cost |
| Guesty task webhooks | `--source webhooks` | replays recorded `task.*` deliveries |
| Breezeway API | `--source breezeway` | `BREEZEWAY_CLIENT_ID/SECRET`; paths per developer.breezeway.io; not verified |
| Turno API | `--source turno` | partner access on request (`TURNO_API_TOKEN`); shape unverified |
| Sensor telemetry JSON | `--source telemetry --file F` | generic shape (see `src/ops/sources/telemetry.py`) |

`wp-price ops sources` shows what is configured and the last run of each.

## Daily use

```bash
wp-price ops profiles                                  # store profile versions
wp-price ops report --from 2026-12-15 --to 2027-01-05  # shadow economics
wp-price ops capacity --date 2027-01-01                # holiday compression
wp-price ops readiness --scan-signals                  # freeze/closure → at_risk
wp-price ops incidents scan && wp-price ops incidents list
wp-price ops incidents approve <id> --action draft_guest_notice --actor <name>
wp-price ops event add --property cloud_9 --system heat --severity critical \
    --state out_of_service --effective-to 2026-12-24 --actor <name>
wp-price compliance check
wp-price owner-receipt --owner northwoods --month 2026-12
```

## Open operator inputs

These don't block anything; each is marked `TODO(operator-confirm)` in config.

- real turnover minutes, crew size, rates, laundry mode, hot tubs
- crew roster and holiday coverage
- STR jurisdiction for 312 and 300 Northwoods (Cloud 9 is set to Fraser, unconfirmed)
- management fee per owner
- which task system is actually in use
- responsible-agent and emergency contacts (enter them as credentials)
- a person to review each compliance rule pack
