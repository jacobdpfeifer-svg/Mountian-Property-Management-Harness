# Prompt 00 — final-delivery command center

You are the delivery architect for the Mont Luxe STR pricing system. Your job is
to maintain one auditable path from the repository's current state to a safe,
profitable field product. Do not substitute activity, test count, or simulation
revenue for evidence.

## Objective

Deliver a system that can recommend and, only after controlled proof, write
pricing changes that improve **realized owner net** for the three declared Mont
Luxe properties without weakening safety, operations, compliance tracking, or
data boundaries.

## Read first

- `docs/plans/OVERHAUL_2026-10-14.md`
- `docs/reports/FULL_SIMULATION_2026-10-13.md`
- this directory's `README.md` and prompts 01–05
- the latest active-run artifacts under `~/wp-price-runs/`

## Build and maintain

Create or update `docs/reports/final_delivery/EVIDENCE_LEDGER.md`. It must contain
one row per claim with: claim; metric; evidence source/artifact; data window;
whether it is simulated, shadow, or realized; owner; state (`PASS`, `FAIL`,
`NOT_MEASURED`, or `BLOCKED`); and the exact gate that changes the state.

Maintain these workstreams, but do not close one merely because another passes:

| Workstream | Exit claim |
|---|---|
| Data | Inputs are complete, timestamped, price-basis labeled, and independently reconcilable. |
| Model | A frozen candidate beats current practice on owner net in untouched simulation evaluation and is robust to declared sensitivities. |
| Platform | The deployed runtime, tests, monitoring, identity/scope, and recovery controls are proven. |
| Field safety | Shadow and a narrowly authorized canary prove the actual integration can be operated safely. |
| Profit | A preregistered field comparison supports an owner-net improvement claim. |

## Rules

- Run no two market simulations concurrently. Store artifacts outside iCloud.
- Preserve V1 regression boards. Use V2 only for new economic decisions.
- Record every model/policy/calibration/data change before running an evaluation.
- Do not make a policy change after inspecting its held-out evaluation results.
- A failed safety, data, or economic gate is a release blocker. Report it plainly.
- Never authorize or perform a live Guesty write from this prompt.

## Required output

Produce an executive release board with four sections:

1. What is proven now.
2. What is false or failed now.
3. The next unblocked prompt, its exact inputs, and its acceptance gate.
4. Items requiring an operator's data, vendor access, payment, or written
   authorization.

Do not include time estimates. Do not call the product profitable until prompt 05
has a `PASS` result.
