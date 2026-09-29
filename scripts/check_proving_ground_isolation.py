#!/usr/bin/env python3
"""Fail if proving_ground_exam imports forbidden engine modules."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAM = ROOT / "proving_ground_exam"
FORBIDDEN = ("src.bookprob", "src.compose", "src.conditions", "src.elasticity")


def main() -> int:
    violations: list[str] = []
    for path in EXAM.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name.startswith(f) for f in FORBIDDEN):
                        violations.append(f"{path}: import {alias.name}")
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(node.module.startswith(f) for f in FORBIDDEN):
                    violations.append(f"{path}: from {node.module}")
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("proving_ground_exam isolation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
