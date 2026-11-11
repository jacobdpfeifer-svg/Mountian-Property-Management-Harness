# Final audit — testrun run 2 (priced-year blind→freeze→reveal)

Canonical orchestrator record: `.testrun_runs/final_audit/FINAL_AUDIT.md`

This file is an operator-visible copy. See that path for the full disposition table,
test commands, and shadow-mode plan.

**Summary:** Run 2 priced 311 / 328 / 321 available nights for Summit, Overlook, and
Cloud 9 with scoped read-only Guesty seeds. All three exports show the same mechanism:
low-confidence deference (~75% weight on listed rate), weak ceilings, and uncalibrated
bookprob. They do **not** prove revenue superiority over Guesty.

**Implemented on main after the freezes (verified this session, not re-run on exports):**

- Weak ceiling no longer replaces decrease caps (`final_clamped_price` + tests).
- Winter Park–only curated comps in `data/scrape/comps.csv` (removed fake Breck/Vail ids).
- `evidence_kind=guesty_readonly` on scoped Guesty calendar sync (+ test).

Guesty write count: 0

## Orchestrator audit completion

Reports fully reviewed: `TESTRUN_312_northwoods.md`, `TESTRUN_300_northwoods.md`, `TESTRUN_cloud9.md`.
