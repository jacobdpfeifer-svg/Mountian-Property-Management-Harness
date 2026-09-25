# Blind-then-reveal test-run harness — three independent property agents

A **two-phase, blind→freeze→reveal experiment surrounded by a production-readiness gate.**
Each agent runs the Mont Luxe pricing engine end-to-end on one property, blind to Guesty,
freezes and hashes its full 365-day output, and only then reveals Guesty + the generic
Winter Park/Fraser market to judge where and why the engine diverges. Output is **findings
and thesis-gated proposals only — no edits.**

## Automated launch

To run this workflow from a Cursor agent, feed
`docs/testrun/TESTRUN_WORKFLOW_PROMPT.md` verbatim to a fresh session. That prompt is
the operator-facing contract: sequential isolation, blind→freeze→reveal, report gates,
then final audit. The next execution is **run 2** of this harness — a first run was
already completed, committed, and pushed; treat those artifacts as prior context, not
as this session's output.

The executable orchestration layer is `scripts/run_testruns.py`. It launches the three
property prompts **sequentially**, each in a disposable copy of the repository, and keeps
checkpoint state under `.testrun_runs/`. After every property report passes its integrity
gate, one new final-audit session reads all three reports, researches their proposals, and
may apply evidence-backed improvements to the main repository. It also writes
`.testrun_runs/final_audit/FINAL_AUDIT.md`.

Configure the command used to start an agent with `TESTRUN_AGENT_CMD`, or pass
`--agent-cmd`. The prompt is sent on stdin; `{workspace}`, `{prompt}`, `{property_id}`,
and `{report}` are available as optional command placeholders. For example:

```bash
TESTRUN_AGENT_CMD='codex exec --full-auto -' \
  python3 scripts/run_testruns.py run
```

Inspect or resume after an interruption with:

```bash
python3 scripts/run_testruns.py status
python3 scripts/run_testruns.py run
```

The runner stops safely on an agent failure or an incomplete report and preserves the
checkpoint; it never advances to reveal or synthesis on partial evidence. This is the
important operational distinction between “does not stop until complete” and silently
continuing after a failed blind run. Use `--rerun` only when intentionally replacing a
completed property session. The final audit is the only session launched with the main
repository as its writable workspace.

Motivation: the historical `docs/reports/GUESTY_RETROSPECTIVE.md` `-$62/night` number was
produced with **zero comps, zero forward pacing, and a survivorship-biased estimator** — the
engine was graded blindfolded on a curve that could only bend down. These runs fix the comp
gap (each agent scrapes its own), enforce a blind boundary (freeze + hash before reveal), and
drop the rigged estimator in favor of reasoning + evidence-classified divergence.

## The three prompts (self-contained; launch one agent per file)
| Prompt | Property | property_id | Owner |
|---|---|---|---|
| `TESTRUN_312_northwoods.md` | 312 Northwoods | `summit_haus` | `northwoods` |
| `TESTRUN_300_northwoods.md` | 300 Northwoods | `overlook_ridge` | `northwoods` |
| `TESTRUN_cloud9.md` | Cloud 9 | `cloud_9` | `cloud9` |

Run window (all three): **2026-09-24 → 2027-09-23 inclusive** (next 365 stay dates).

## What these runs CAN and CANNOT establish
The agents can establish: whether the engine runs end-to-end per property; whether prices are
grounded in fresh, independently gathered market evidence; whether the reasoning is internally
coherent; where it differs from Guesty and the broader market; and which differences are
justified, questionable, or caused by missing/stale data.
They **cannot** establish revenue superiority from next-year prices alone — future nights have
no booking outcomes. That requires the **forward shadow-mode track** (below).

## Experimental blockers baked into every prompt (verify, do not fix)
1. Never run unscoped `recommend` / `push` / `audit` / `export` — the DB contains
   `creekside_haven` (`src/db/__init__.py:234`). Every command is scoped to the target property.
2. Guesty is **read-only**. Never `wp-price push` (any adapter), never
   `GuestyClient.set_rate` / `--confirm-live-write`, never PUT/POST/PATCH/DELETE the
   Guesty Open API except OAuth. Pulls (`sync-guesty`, calendar GET) are allowed;
   writing prices or min-stay back is forbidden. Reports must include
   `Guesty write count: 0`.
3. The `round_price_conservative` ceiling-overrun defect may push valid recommendations past
   the ceiling and fail the independent audit — classify, don't patch.
4. Pacing history is incomplete → booking-probability output must be reported as weak /
   uncalibrated.
5. Existing Guesty data must not be inspected before each blind run is **frozen and hashed.**

## Two operational decisions for you
**1. Isolation — required.** Each agent uses its own disposable DB (`--db /tmp/testrun_<id>.db`)
or its own worktree, so the three never share state. (Otherwise: collided tables, poisoned
market sweep.)

**2. Comp independence vs. anti-bot risk.** Each agent scraping its own full ~280-listing
sweep matches "find their own comps," but three concurrent sweeps of the same market may trip
rate-limiting, and the scraper discards suspect sweeps wholesale. Alternative: one shared raw
sweep, each agent independently *curates* its own comp set + does its own calculations. The
prompts default to independent sweeps and tell agents to treat a blocked sweep as a finding
(not retry-hammer). Say the word to switch to the shared-raw-sweep variant.

## A finding baked into the design
The engine **is not currently able to run fully blind to Guesty**: the composer defers ~75%
toward Guesty's listed price on low-confidence nights (`src/compose/__init__.py` step 4) and
the booking-prob reference falls back to it (`src/bookprob`). Each prompt asks the agent to
measure how often its numbers were pulled toward Guesty and treat that as a first-class result.

## Reconvene plan (me, after all three return)
Cross-property synthesis: below-ceiling / below-market pricing in shoulder+summer on **all
three** → the elasticity betas (config-level), not per-property quirks. Property-specific
divergence points elsewhere (Cloud 9 cold-start; the twins as a consistency check).

## Separate track (the only revenue-truth experiment) — forward shadow mode
After these reports, the real test: run the engine in shadow mode, keep Guesty's actual price
live, record the engine's recommendation daily, and record bookings, booking lead time,
cancellations, occupancy, ADR, and realized RevPAN — evaluated by season, property, lead-time
bucket, and price-distance bucket. That is the first experiment capable of testing whether the
niche Colorado signals produce better *outcomes* than Guesty. Not attempted in these three runs.
