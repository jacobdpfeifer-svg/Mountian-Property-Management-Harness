#!/usr/bin/env python3
"""Repeatable quality gates. mypy is advisory this pass and does not fail the run."""

from __future__ import annotations

import compileall
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(argv: list[str], *, advisory: bool = False) -> int:
    print(f"+ {' '.join(argv)}")
    result = subprocess.run(argv, cwd=ROOT)
    if result.returncode != 0 and advisory:
        print(f"ADVISORY: {' '.join(argv)} exited {result.returncode} (not failing this pass)")
        return 0
    return result.returncode


def main() -> int:
    src = ROOT / "src"
    scripts = ROOT / "scripts"
    if not compileall.compile_dir(str(src), quiet=1):
        print("compileall failed for src/")
        return 1
    if not compileall.compile_dir(str(scripts), quiet=1):
        print("compileall failed for scripts/")
        return 1
    print("compileall OK")

    pytest = [sys.executable, "-m", "pytest", "--cov=src", "--cov-report=term-missing"]
    if _run(pytest) != 0:
        return 1

    if _run([sys.executable, "-m", "vulture", "src", "scripts"]) != 0:
        return 1

    check = ["uv", "pip", "check"] if shutil.which("uv") else [sys.executable, "-m", "pip", "check"]
    if shutil.which(check[0]) or check[0] == sys.executable:
        if _run(check) != 0:
            return 1

    audit = [sys.executable, "-m", "pip_audit"]
    _run(audit, advisory=True)

    mypy = [sys.executable, "-m", "mypy", "src"]
    _run(mypy, advisory=True)
    print("QUALITY GATES OK (mypy/pip-audit advisory)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
