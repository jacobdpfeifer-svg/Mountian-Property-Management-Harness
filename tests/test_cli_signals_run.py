"""Regression coverage for `wp-price signals run` (src/cli/main.py::cmd_signals_run).

Step 0's mypy pass flagged src/cli/main.py:626 — `cls(store, **kwargs)` typed
against the *base* `Collector.__init__(self, store, *, sleep=...)`, which only
declares `sleep`, while `kwargs` can carry `fixture_path` (a `Path`). mypy
reports "Argument 2 to 'Collector' has incompatible type '**dict[str, Path]';
expected 'Callable[[float], None]'" because `get_collector` only returns the
base `Type[Collector]`, so mypy can't see that every concrete registered
collector (see src/signals/collectors/regulatory.py, weather.py, enso.py,
flight.py, intent.py) overrides `__init__` to accept `fixture_path`.

This is a real gap in the CLI's static type coverage, but not a runtime bug —
this test exercises the actual code path end to end through `main()` (not just
importing the function) to confirm `cls(store, **kwargs)` really does work at
runtime for a fixture-capable collector, so a *genuine* future incompatibility
here (e.g. a collector's __init__ signature drifting) would show up as a test
failure rather than only as a wall of mypy noise nobody reads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cli.main import main
from src.db import connect


def test_signals_run_regulatory_collector_without_fixture(tmp_path: Path):
    db = tmp_path / "signals.db"
    with pytest.raises(SystemExit) as exc:
        main([
            "--db", str(db), "signals", "run",
            "--collector", "regulatory", "--market", "grand_home",
            "--as-of", "2026-09-01",
        ])
    assert exc.value.code == 0
    with connect(db) as conn:
        row = conn.execute(
            "SELECT status FROM signal_runs WHERE collector = 'regulatory'"
        ).fetchone()
    # No fixture supplied -> the collector still runs end to end (via
    # `cls(store, **kwargs)`, the exact call mypy flags) and records a
    # completed run rather than crashing on the subclass-only `fixture_path`
    # kwarg.
    assert row is not None
    assert row["status"] == "ok"
