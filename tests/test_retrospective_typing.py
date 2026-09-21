"""Regression test for a real mypy-catchable bug class in src/eval/retrospective.py.

Step 0 of the 2026-09-20 production-readiness audit's mypy pass flagged a ~15-error
cluster at src/eval/retrospective.py:562-598: `format_markdown` reused the loop
variable name `s` for three different dataclasses in the same function scope —
`PropertySummary` (the "by property" table), `PropertySummary` again (the "by
owner" table), and `NightScore` (the "example nights" section). mypy infers a
variable's type from its first binding in a function and does not silently accept
a later rebinding to an unrelated type, so it reported the entire `NightScore`
attribute list (`guesty_booked`, `stay_date`, `ceiling_price`, `leakage_kind`, ...)
as "has no attribute" against the earlier-inferred `PropertySummary` type.

At runtime this was harmless (Python's function-level scoping meant each `for`
loop rebound `s` correctly and the existing tests in test_retrospective.py already
exercise this code path without error) — but the shadowing made mypy blind to real
type errors anywhere in this function, in exactly the shape that lets a truly wrong
field name slip through silently in an operator-facing report generator. The fix
renamed the PropertySummary loop variables to `ps`, eliminating the collision.

This test pins that specific bug class: if the shadowing is reintroduced (in this
file or anywhere else that mixes NightScore/PropertySummary in one function), mypy
must report it here so it doesn't ship silently again.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_mypy(*paths: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.stdout + proc.stderr


def test_retrospective_format_markdown_has_no_property_summary_night_score_confusion():
    output = _run_mypy("src/eval/retrospective.py")
    # This is the exact attribute set that leaked from NightScore onto a variable
    # mypy had inferred as PropertySummary. None of these should appear as
    # "has no attribute" errors against PropertySummary any more.
    night_score_only_attrs = [
        "guesty_booked", "guesty_listed", "engine_price", "demand_event",
        "leakage_kind", "leakage_detail", "comp_price", "comp_usable",
        "comp_reason", "approx_comp_price", "ceiling_method",
    ]
    for attr in night_score_only_attrs:
        assert f'"PropertySummary" has no attribute "{attr}"' not in output, (
            f"regression: PropertySummary/NightScore variable-name confusion is "
            f"back for attribute {attr!r}. mypy output:\n{output}"
        )
    assert "Incompatible types in assignment (expression has type \"NightScore\", " \
        "variable has type \"PropertySummary\")" not in output
