# Final profitability gate

Date: 2026-10-20. Status: **NOT_READY_MISSING_DATA**.

Guesty writes this session: **0**. No canary was activated. No realized owner net is claimed.

`NOT_READY_MODEL_FAILED` and `NOT_READY_SHADOW_INCOMPLETE` are also true. They are recorded in `V3_EXPERIMENT_EVIDENCE.md` and `SHADOW_OPERATIONS.md`. The single gate status is missing settled data, because profitability cannot be measured until settlement and owner statements exist. Reconciliation was not failed against a statement; there was no statement to reconcile.

## Evidence

| Report | Result |
|---|---|
| [ECONOMIC_BASELINE.md](ECONOMIC_BASELINE.md) | BLOCKED_ON_EXTERNAL_DATA. 78 reservations and 45 forward calendar days ingested read-only. 0 settled lines. 0 statements. |
| [OWNER_NET_SCORECARD.md](OWNER_NET_SCORECARD.md) | INCOMPLETE for all three homes. Hurdle missing. |
| [SHADOW_OPERATIONS.md](SHADOW_OPERATIONS.md) | Machinery tested. 0 real shadow days. Gate not passed. |
| [V3_EXPERIMENT_EVIDENCE.md](V3_EXPERIMENT_EVIDENCE.md) | Screen REWORK. Evaluation not opened. |
| [CANARY_READINESS.md](CANARY_READINESS.md) | BLOCKED. Authorization not created. |
| [EXTERNAL_BLOCKERS_AND_REQUESTS.md](EXTERNAL_BLOCKERS_AND_REQUESTS.md) | Requests drafted, not sent. |

## Commands and tests

- Freeze and `scripts/screen_gate.py` on 2026-10-20. Decision REWORK. Register `302a3b51dbe6f72d90daf6232ad417fa51d699a9bd0a332e10736932227b9115`.
- Read-only Guesty census and `backfill_guesty` into gitignored `data/profitability_readonly.db`.
- `scripts/quality_gates.py`: 1113 passed, 3 deselected, coverage 80.83%, vulture clean, mypy clean.
- `scripts/scan_repo.py`: 0 problems.
- Migrations discover `0001` through `0008_shadow_outcome_metrics`. The latest migration appends source-fingerprinted actual shadow ADR/RevPAN and later settled-owner-net-per-night observations without rewriting the first outcome. Not applied to an operator production database in this session.

## Source coverage

Guesty read credential was present and used only for listings, calendar, and reservations. Write credential was absent. Accounting, statements, ops costs, certified comps, system cost, and jurisdictions were not supplied. One out-of-scope listing was not imported. Two reservations quarantined `INCONSISTENT:nights`.

## Assumptions

No fee percent, no system cost, no sellable nights, no jurisdiction, and no simulated profit were used as settled facts.

## Unresolved exceptions

Pending Guesty money only. No statement reconciliation. V3 harm not excluded on the screen (mean simulated owner-net delta −5,031; interval −15,911 to +5,848; 3 of 10 pairs favourable). Shadow gate not passed.

## External dependencies

Settlement and owner statements first. Then fee terms, system cost, ops costs, certified comps, and a 30-day shadow runtime. Canary artifacts stay blocked behind those and behind a model that passes a new preregistered evaluation.

## Next action

Import settlement lines and owner statements with the templates in `config/data_mapping/`. Do not write a rate, do not open V3's held-out seeds, and do not start a canary.

## Answers

1. Settled owner net is not known for Summit Haus, Overlook Ridge, or Cloud 9. The read-only pull has pending booking lines only. One Overlook Ridge stay traces as far as a pending ledger and then stops, with no statement.
2. The incremental owner net per available night required to pay for the system is not calculated. Annual system cost and annual sellable nights were not supplied.
3. The V3 pricing model is not eligible for a controlled canary. The screen decision is REWORK, and evaluation was not opened.
4. The single blocker that most limits profitability proof is the absence of channel settlement lines and monthly owner statements.
5. The operator should export those settled facts and import them through the templates. The operator should not push a live price, create a reservation, change availability, treat the shadow or the simulator as realized profit, or authorize a canary on this candidate.
