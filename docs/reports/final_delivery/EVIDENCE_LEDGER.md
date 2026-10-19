# Final-delivery evidence ledger

Last reviewed: 2026-10-15.  This ledger is deliberately conservative: simulated
results are never treated as realized owner profit, and an absent external feed
is not inferred from code or tests.

| Claim | Metric | Evidence source / artifact | Data window | Evidence kind | Owner | State | Gate that changes state |
|---|---|---|---|---|---|---|---|
| V2 calibration is usable for measured targets | 8 measured checks pass; shoulder ADR is explicitly unmeasured | `~/wp-price-runs/full_sim_20261015_d291c60/v2_calibration_validation.json` | 10 simulated seeds; local aggregate rate card | simulated | Model lead | PASS | Re-run when calibration or approved rate-card input changes; shoulder becomes measured only with >=10 real booked nights. |
| V2 calibration fully covers every property/season/lead target | Measured coverage for all declared targets | Same artifact: `booked_adr_shoulder_spring` has 0 real nights | Current local export | simulated / first-party aggregate | Data lead | NOT_MEASURED | Obtain and reconcile sufficient shoulder-season history. |
| Frozen pace candidate improves simulated owner net over current practice | Paired owner-net interval versus `current_practice`, 25 untouched seeds | Five-seed first look: `v2_screen_pace_learned_owner_net/audit.json`; plan §Progress log | normal, seeds 1–5 | simulated screen | Model lead | FAIL | A preregistered, frozen candidate must satisfy the material-harm gate on untouched paired seeds and declared stress worlds. Do not retune after opening them. |
| Candidate is ready to enter shadow | Calibration, held-out non-harm, stress, reliability, and production-faithful gates | No held-out V2, reliability, or production-faithful candidate evidence | N/A | simulated | Model lead | BLOCKED | Prompt 02 decision record `ADVANCE_TO_SHADOW`; currently no such record is justified. |
| Repository quality baseline passes | Isolation, preflight, quality, slow, and ops suites | `gate_isolation.log`, `gate_preflight.log`, `gate_quality.log`, `pytest_slow.log`, `ops_tests.log` under active run | 2026-10-15 | platform test | Platform lead | PASS | Re-run clean-environment release suite after implementation or dependency changes. |
| Production runtime is deployable and rollbackable | Immutable release, deployed SHA, clean-runtime proof, rollback proof | Preflight warns `DEPLOYED_SHA` is absent; no release manifest/rollback artifact | Current machine | platform | Platform lead | FAIL | Clean build/deploy/rollback demonstration with source, policy, calibration, schema, and dependency hashes. |
| Live writes cannot happen unsafely | Tested global kill switch, final-boundary checks, canary/read-back/rollback proof | No global kill-switch or live canary evidence identified | N/A | platform / field | Safety lead | BLOCKED | Complete Prompt 03 controls and Prompt 04's written authorization, staging rollback, and read-back gates. |
| Required portfolio data is complete and reconcilable | Exact three-listing mapping; >=99% reservation and money reconciliation | Local aggregate `data/exports/rate_card.yaml` only; no PMS/channel/statement/ops feeds or reconciliation dossier | Current local export | data | Data lead / operator | BLOCKED | Operator supplies approved read-only exports and contracts; demonstrate field-level reconciliation and exceptions. |
| Realized owner net improves | Preregistered realized owner net per eligible available night | No field cohort, decision ledger, settlement join, or financial analysis | N/A | realized | Outcome analyst / operator | NOT_MEASURED | Prompt 05 preregistration, settled financial reconciliation, and benefit/no-material-harm analysis pass. |
| Guesty write authorization exists | Written property/date/move/count/approver/rollback scope | No authorization artifact | N/A | field safety | Operator | BLOCKED | Operator provides the exact written scope after prompts 01–03 and shadow pass. |

## Audit notes

- The 2026-10-15 active run completed its gates, V2 calibration validation, a
  five-seed V2 benchmark screen, and a five-seed pace-candidate screen. It is
  **not** a held-out policy evaluation.
- The pace candidate is better than the legacy default engine in that screen,
  but it loses to `current_practice`; the release comparator is current
  practice, not the legacy engine.
- Older V1 figures remain regression evidence only. Their market price level
  was materially below the real listing/booking level and cannot support a V2
  economic release decision.
