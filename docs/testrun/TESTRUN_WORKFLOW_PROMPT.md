# Cursor prompt — run the blind-then-reveal testrun workflow

Feed this file verbatim to a fresh Cursor agent in the **main repository**. The agent
is the orchestrator and the property diagnostician. Do not hand the work back as a
plan. Execute until every property report passes its integrity gate and the final
audit record exists, or stop at the first failed gate.

---

You are running the Mont Luxe Collection **blind→freeze→reveal** diagnostic harness.

Read first, in order:

1. `docs/testrun/README_TESTRUN.md`
2. `docs/testrun/TESTRUN_312_northwoods.md`
3. `docs/testrun/TESTRUN_300_northwoods.md`
4. `docs/testrun/TESTRUN_cloud9.md`
5. `scripts/run_testruns.py` (orchestration contract, report gates, isolation)

Then execute the workflow below. Property sessions are **read-only diagnostics**.
The final audit is the only session allowed to change the main repository.

## Goal

For each of `summit_haus`, `overlook_ridge`, and `cloud_9`, produce a complete
end-to-end diagnostic of whether the pricing engine yields **defensible,
comp-grounded, explainable** recommendations. Then synthesize and, only in the
final audit, apply evidence-backed fixes.

Do **not** claim the engine beats Guesty on revenue. Next-year prices have no
booking outcomes. Flag forward shadow-mode as the next experiment; do not run it.

Run window for all three properties: **2026-09-24 through 2027-09-23 inclusive**.

## Second-pass context

This is the **second** execution of this same testrun workflow. A first complete run
already finished, was **committed, and was pushed** to origin. That first pass is
historical evidence, not this session.

Use it as context only:

- Inspect git (`git log`, `origin/main`, prior `docs/reports/TESTRUN_*.md`,
  `.testrun_runs/final_audit/FINAL_AUDIT.md` if those blobs exist on the remote
  or in history). Do not pretend the engine has never been through this harness.
- Do **not** re-litigate or re-implement fixes that already landed in that
  commit/push unless this run produces new evidence they are wrong or incomplete.
- Still run a **full fresh** blind→freeze→reveal. Do not copy old export hashes,
  row counts, prices, or verdicts into the new reports.
- After this run's freeze, you may compare against the first-run reports as a
  **delta** (what changed, what persisted, what the first audit already fixed).
- Label every new report as **run 2**. Same output paths are fine; state in the
  executive verdict and orchestrator completion that this supersedes the first
  pushed run rather than being the original.
- The incomplete local `.testrun_runs/summit_haus` session is **not** run 1.
  Resume it only if it belongs to *this* second pass.

## Hard rules (never violate)

- Sequential only. Finish and gate one property before starting the next.
  Order: `summit_haus` → `overlook_ridge` → `cloud_9` → final audit.
- Isolated disposable DB per property: `--db /tmp/testrun_<property_id>.db`.
  Print the DB path at the top of that property's report.
- Every `recommend`, `audit`, `export`, and `health` invocation must include
  `--property <property_id>`. If a command would touch `creekside_haven`, stop
  that command and record a scope failure.
- **Guesty is read-only for this entire workflow, including the final audit.**
  Never add, update, or delete prices, min-stay, availability, or any other
  listing field in Guesty. Live calendars must be unchanged when you finish.
  See **Guesty API — read only** below.
- Blind boundary: do not inspect Guesty current prices, reservations, calendar
  rates, or `docs/reports/GUESTY_RETROSPECTIVE.md` as a price source **until that
  property's export is frozen and SHA-256 hashed**.
- Do not use Guesty rates as an input, anchor, validation target, or comp during
  the blind phase.
- Property sessions: do not modify tracked source, policy YAML, portfolio YAML,
  schemas, or production data. Suggestions only. The only file you create is the
  report.
- Treat a blocked or discarded market sweep as a finding. Do not retry-hammer the
  scraper.
- If a command fails, classify it in the report and continue through remaining
  **safe** phases. Do not invent prices for dates the engine cannot price.
- Do not start the final audit until all three reports pass the integrity gate.

## Guesty API — read only

Guesty is the live system of record for three real houses. This experiment may
**read** it. It must **never write** it. No recommended price, floor, ceiling,
min-stay, or availability change may land on a Guesty listing.

Allowed (GET / pull into the **local** disposable DB only):

- `wp-price sync-guesty` (listings, calendar, reservations → SQLite)
- `GuestyClient` read helpers (`listings`, calendar GET, reservations GET,
  `current_rate`)
- After freeze: inspecting `nightly_inventory` that was pulled earlier

Forbidden — do not run, import-and-call, curl, or “just try”:

- `wp-price push` with any adapter (`guesty` **or** `dry_run`)
- `--adapter guesty`, `--confirm-live-write`, or any canary write
- `GuestyClient.set_rate` / `push_rate` / `push_recommendations`
- HTTP `PUT`, `POST`, `PATCH`, or `DELETE` to `open-api.guesty.com` except the
  OAuth token request
- Direct writes to
  `/v1/availability-pricing/api/calendar/listings/{id}`
- Scripts, notebooks, or REPL snippets that set nightly price or min nights
- Using `wp-price recommend` as if it published prices — it must persist only
  to the local `--db`, never to Guesty

If a command, flag, or method name contains `push`, `set_rate`, `live-write`,
or a non-GET Guesty URL, stop and record it as a protocol violation instead of
running it. Prefer comparing against already-synced `nightly_inventory` over
opening a new Guesty client.

## Isolation

Prefer a disposable worktree or copy under `.testrun_runs/<property_id>/workspace`
(same isolation `scripts/run_testruns.py` uses). If you stay in the main repo,
still use a unique `/tmp/testrun_<id>.db` and write only that property's report.

Do not share tables, scrapes-as-DB-state, or recommendation rows across
properties. Independent curation and calculation is required even if a sweep is
reused as raw evidence after a block.

## Checkpointing

Maintain `.testrun_runs/state.json` conceptually the same way the runner does:

- `properties.<id>.status`: `running` | `complete` | `failed`
- `properties.<id>.db`, `prompt`, `workspace`
- copy each passing report to `docs/reports/<report_name>` in the main repo

If a prior session already exists under `.testrun_runs/`, inspect
`.testrun_runs/state.json` and that property's `prompt.md` / report. Resume the
first incomplete property. Do not `--rerun` a complete property unless the
operator asked to replace it.

## Per-property session

For each property, treat the matching `docs/testrun/TESTRUN_*.md` as the full
spec. Overlay this execution contract.

| property_id      | prompt                              | report                             | db                                 |
|------------------|-------------------------------------|------------------------------------|------------------------------------|
| `summit_haus`    | `TESTRUN_312_northwoods.md`         | `docs/reports/TESTRUN_312_northwoods.md` | `/tmp/testrun_summit_haus.db` |
| `overlook_ridge` | `TESTRUN_300_northwoods.md`         | `docs/reports/TESTRUN_300_northwoods.md` | `/tmp/testrun_overlook_ridge.db` |
| `cloud_9`        | `TESTRUN_cloud9.md`                 | `docs/reports/TESTRUN_cloud9.md`         | `/tmp/testrun_cloud_9.db` |

### Phase 0 — preflight (no Guesty prices)

Read the files listed in that property prompt. Run `pytest -q`, mypy per
`pyproject.toml`, and `python scripts/production_preflight.py`. Classify findings
only: experiment blocker · measurement limitation · recommendation-quality risk ·
operational-risk finding · low-priority improvement. Verify, do not fix:

- unscoped property selection / `creekside_haven`
- `round_price_conservative` ceiling overrun
- incomplete pacing history → booking probability is **weak / uncalibrated**
- missing historical contemporaneous comp snapshots
- 365-day market coverage

### Phase 1 — blind data acquisition

Initialize the isolated DB. Load only permitted non-Guesty inputs. Discover comps
for a luxury 5-bedroom profile across peak_ski, early_winter, shoulder_spring,
and summer. Scrape `wp-price scrape-comps --horizon 365` into `comp_snapshots`
and whole-market `market_snapshots`. Run signals and
`wp-price health --property <id> --db <db>`.

Generic market stats (p25/p50/p75, n, filters, freshness) must be independent of
the curated comp set. Never silently substitute the curated-comp median for the
generic market average.

### Phase 2 — blind recommend, export, FREEZE

```bash
wp-price recommend \
  --property <id> \
  --from 2026-09-24 \
  --to 2027-09-23 \
  --limit 500 \
  --technical \
  --db /tmp/testrun_<id>.db
```

Then:

```bash
wp-price export \
  --property <id> \
  --from 2026-09-24 \
  --to 2027-09-23 \
  -o data/exports/testrun_<short>.csv \
  --db /tmp/testrun_<id>.db
```

Record SHA-256 and row count in the report **before** any Guesty reveal. That
hash is the integrity boundary. Nothing after it may alter the blind run.

Export short names: `testrun_312.csv`, `testrun_300.csv`, `testrun_cloud9.csv`.

### Phase 3 — reveal (only after freeze)

Read-only Guesty forward prices from `nightly_inventory` (inspect schema first).
Compare each recommendation to Guesty listed, generic market p25/p50/p75,
curated comps, floor/ceiling, and stated reason. Classify divergences with the
vocab in the property prompt.

Measure how often compose/bookprob pulled toward Guesty's listed price (~75%
deferral on low-confidence nights). That pull is a first-class result.

### Phase 4 — analytical stress tests

No code changes. For the cases in the property prompt, label each
robust · highly sensitive · unsafe · unmeasurable.

### Phase 5 — write the report

Write the exact report path. Required sections (all of them):

1. Executive verdict
2. Exact commands + data sources
3. Blind-run integrity (hash + row count)
4. Data coverage and freshness
5. Full-year recommendation summary
6. Comparison with Guesty
7. Comparison with generic market averages
8. Largest divergences
9. Reasoning-quality assessment
10. Audit and safety findings
11. Stress-test results
12. Proposed changes, ranked
13. External tools worth considering (thesis-gated: problem, cited evidence,
    why the repo cannot cover it, benefit, cost, new failure modes, validation
    plan, verdict test/shadow/adopt/reject)

End with a literal heading `## Orchestrator completion` containing: DB path,
export hash, export row count, blind-freeze timestamp, confirmation that every
report section was addressed, and the literal sentence
`Guesty write count: 0 (read-only; no rates pushed)`. Confirm no tracked files
were changed.

Property-specific probes (do not skip):

- `summit_haus`: is summer/shoulder underpriced by elasticity betas vs genuinely
  soft demand?
- `overlook_ridge`: are the Northwoods twins treated as twins, and is any
  divergence evidence-backed?
- `cloud_9`: thin history / cold-start; keep Cloud 9 in shared `grand_home`
  unless a Fraser-only market is only a Phase 5 proposal.

## Integrity gate (required before the next property)

The report file must exist and, case-insensitive, contain:

- `## Orchestrator completion`
- `blind`
- `hash`
- `row count`
- `Guesty write count: 0`

Copy the passing report to the main-repo `docs/reports/` path. Then start the
next property.

## Final audit (main repo only, after all three pass)

Read every character of the three reports, not just executive summaries. Read
`docs/testrun/README_TESTRUN.md`, the production-readiness audit, and the
source/tests for each finding. Research externally where a proposal requires it.
Reconcile contradictions. Implement only necessary, safe, evidence-backed
improvements. Add or update tests for every code change. Do not alter the three
completed reports or frozen exports. Do not violate the blind-run protocol.

Do not push rates, run a Guesty canary, or otherwise write to the live PMS while
implementing repo fixes. Guesty remains read-only.

Write `.testrun_runs/final_audit/FINAL_AUDIT.md` with: report-by-report coverage,
every finding disposition, researched evidence, files changed, tests run and
results, rejected proposals, remaining risks, a forward shadow-mode plan, and
`Guesty write count: 0`.

Include the literal heading `## Orchestrator audit completion` and list each
report filename under `Reports fully reviewed`
(`TESTRUN_312_northwoods.md`, `TESTRUN_300_northwoods.md`, `TESTRUN_cloud9.md`).

## Optional CLI wrapper (only if a headless agent command exists)

```bash
python3 scripts/run_testruns.py status
python3 scripts/run_testruns.py run --agent-cmd '<launcher that reads the prompt on stdin>'
```

Placeholders: `{workspace}`, `{prompt}`, `{property_id}`, `{report}`. Resume
after a stop with `python3 scripts/run_testruns.py run`. Use `--rerun` only to
replace a completed property session. In this Cursor chat, prefer executing the
phases yourself over spawning a nested agent unless the operator supplied
`--agent-cmd`.

## Done when

- Three reports exist in `docs/reports/` and each passed the gate
- `.testrun_runs/final_audit/FINAL_AUDIT.md` exists and passed its gate
- Property sessions changed no engine/policy files; only the final audit did,
  with tests
- Guesty calendars and rates were never written (write count 0)

