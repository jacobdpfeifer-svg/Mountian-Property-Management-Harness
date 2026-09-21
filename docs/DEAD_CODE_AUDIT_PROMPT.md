# Dead-Code & Overlap Audit — Agent Prompt

Reusable prompt for spawning an agent (or running yourself) to audit this repo
(Pfeifer Optimization STR pricing engine) for dead code and duplicated/overlapping
functionality, then clean it up. Paste the block below as the task prompt.

**Before running**: commit or stash any in-progress changes, or run this in an
isolated worktree/branch — the agent will delete and rewrite files.

---

## Prompt

You are auditing the "Pfeifer Optimization" STR pricing engine repo for dead code
and overlapping/duplicated functionality, and removing what you find. Work like
someone about to inherit this codebase who needs to trust every file that remains.

### 1. Build a map of what's actually alive

Before deleting anything, establish ground truth by *exercising* the code, not just
reading it:

- Read `pyproject.toml` / `wp_str_pricing.egg-info/entry_points.txt` to find the
  real CLI entry points, then run `src/cli/main.py`'s subcommands end-to-end
  (`--help` on every subcommand, then a real run against `data/sample/` or
  `data/cloud9/` fixtures) so you see which modules under `src/` actually get
  imported and executed.
- Run the full test suite (`pytest`) and capture which `src/` modules each test
  file exercises. Note any test file that imports something no longer wired into
  the CLI or into another module — that's a signal, not a verdict.
- Cross-reference `scripts/*.sh` and `scripts/*.py` against what they actually
  invoke (some may call CLI commands or module paths that no longer exist).
- For every top-level package under `src/` (`audit`, `bookprob`, `ceiling`,
  `compose`, `comps`, `db`, `elasticity`, `eval`, `explain`, `features`,
  `guardrails`, `ingest`, `leakage`, `min_stay`, `pacing`, `pms`, `resort`,
  `scrape`, `signals`, `cli`), find every import site (`grep -rn "from src.<pkg>"
  src/ tests/ scripts/`). A package/module with zero import sites outside its own
  file and outside tests is a dead-code candidate — but confirm before deleting
  (see step 3).

### 2. Find overlap, not just silence

Dead code isn't only "never imported" — it's also "duplicated" or "superseded."
Specifically look for:

- **Near-duplicate modules** solving the same problem twice, e.g. compare
  `src/eval/backtest.py` vs `src/eval/retrospective.py`, `src/pms/sync.py` vs
  `src/pms/webhooks.py`, and anything in `src/signals/collectors/` vs
  `src/signals/collector.py` — read both, decide if one is the live path and the
  other a superseded draft, or if they should be merged.
- **Duplicate config/data artifacts** that look like accidental copies rather than
  intentional variants — anything named with a trailing " 2" or "-copy" (e.g. a
  stray `<name> 2.db`/`<name> 2` file), stale `.db`/`.db.icloud-backup` snapshots
  under `data/`, and `build/lib/src/` (a build artifact directory that duplicates
  `src/` and should not be tracked or should be gitignored).
- **Duplicate logic inline vs. in a shared module** — grep for repeated helper
  functions (e.g. date/price formatting, YAML/CSV loading) defined separately in
  more than one file instead of imported from `src/utils.py` or `src/config.py`.
- **Orphaned docs** in `docs/` and `docs/rules/` that describe a workflow or
  module that no longer exists in `src/` — flag these even though they're not
  code, since a stale runbook is as dangerous as dead code.
- **Unused fixtures/tests** in `tests/fixtures/` not referenced by any test file.

### 3. Verify before removing

For every candidate, confirm dead/duplicate status with at least two of:
`grep -rn` for the symbol/module name across `src/`, `tests/`, `scripts/`,
`docs/`, and `config/`; checking `git log --follow` on the file to see if it's
recent/in-progress work; running the test suite with the file temporarily
removed (or via `python -c "import module"` failing loudly) to confirm nothing
breaks.

Do not delete:
- Anything referenced by `config/policies/*.yaml`, `config/resort/*.yaml`, or
  `config/portfolio/*.yaml` even if the only reference is a string key.
- Sample/fixture data under `data/sample/`, `data/cloud9/`, `data/dec2023/` even
  if no current test reads every column — these are reference datasets, not code.
- Anything the CLI `--help` tree still lists, even if you personally didn't
  exercise that branch.

### 4. Clean it up

- Delete confirmed-dead modules, functions, scripts, and stray duplicate files.
- Where two modules overlap, consolidate into one and update every import site
  (`grep -rn` again afterward to confirm no dangling imports remain).
- Remove stale generated/cache directories that shouldn't be tracked
  (`__pycache__/`, `.pytest_cache/`, `build/`) and make sure `.gitignore` covers
  them so they don't reappear in `git status`.
- Update or delete any doc that referenced removed code.

### 5. Prove it still works

- Run `pytest` — everything must still pass.
- Re-run the CLI smoke test from step 1 against the same sample data and confirm
  output is unchanged (or note deliberately changed behavior).
- Run `git status` / `git diff --stat` and produce a short report: what was
  removed, what was merged into what, and why each removal was safe (cite the
  grep/test evidence from step 3).

Report the findings and the diff — don't just silently commit. Flag anything you
were unsure about (e.g. "looks dead but is dated within the last week of commits")
instead of deleting it.
