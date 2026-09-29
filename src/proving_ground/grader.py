"""Deterministic grader — scores manifests against hash-locked thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.proving_ground.thresholds import LEVEL_THRESHOLDS


@dataclass(frozen=True)
class GradeResult:
    level: int
    passed: bool
    failed_gates: list[str]


def grade_manifest(manifest: dict[str, Any]) -> GradeResult:
    level = int(manifest["level"])
    gates = manifest.get("gates") or []
    failed = [g["name"] for g in gates if not g.get("passed")]
    return GradeResult(level=level, passed=not failed, failed_gates=failed)


def format_scoreboard_md(rows: list[dict[str, Any]], *, engine_version: str) -> str:
    lines = [
        "# Proving Ground Scoreboard",
        "",
        f"Engine version: `{engine_version}`",
        "",
        "| Policy | Revenue | Regret vs oracle |",
        "|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['policy_id']} | {row['revenue']:.2f} | {row['regret_vs_oracle']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"
