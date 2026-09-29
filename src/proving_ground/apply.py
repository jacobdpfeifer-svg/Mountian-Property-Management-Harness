"""Fix Card apply gate — refuses without operator decision on record."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS_PG = ROOT / "docs" / "proving_ground"
PROPOSALS = DOCS_PG / "proposals"
RECEIPTS = DOCS_PG / "receipts"
QUEUE = DOCS_PG / "APPROVAL_QUEUE.md"


@dataclass(frozen=True)
class FixDecision:
    fix_id: str
    decision: str
    decided_at: str
    notes: str


def parse_queue_decision(fix_id: str) -> FixDecision | None:
    if not QUEUE.exists():
        return None
    text = QUEUE.read_text(encoding="utf-8")
    if fix_id not in text:
        return None
    block = text.split(f"## Fix Card {fix_id}")[-1].split("## Fix Card")[0]
    m = re.search(r"Operator decision:\s*(\w+)", block, re.I)
    if not m:
        return None
    decision = m.group(1).strip().lower()
    if decision == "pending":
        return None
    date_m = re.search(r"Decision date:\s*([0-9-]+)", block)
    notes_m = re.search(r"Operator notes:\s*(.+)", block)
    return FixDecision(
        fix_id=fix_id,
        decision=decision,
        decided_at=date_m.group(1) if date_m else date.today().isoformat(),
        notes=notes_m.group(1).strip() if notes_m else "",
    )


def apply_fix(fix_id: str) -> Path:
    decision = parse_queue_decision(fix_id)
    if decision is None:
        raise PermissionError(
            f"Refusing apply for {fix_id}: record Operator decision in {QUEUE} first."
        )
    proposal = PROPOSALS / f"{fix_id}.md"
    if not proposal.exists():
        raise FileNotFoundError(f"Missing proposal {proposal}")

    RECEIPTS.mkdir(parents=True, exist_ok=True)
    receipt_path = RECEIPTS / f"{fix_id}-receipt.md"
    receipt_path.write_text(
        "\n".join([
            f"# Receipt — {fix_id}",
            "",
            f"Decision: **{decision.decision}** on {decision.decided_at}",
            f"Notes: {decision.notes or '(none)'}",
            "",
            f"Proposal: `{proposal.relative_to(ROOT)}`",
            "",
            "## Outcome",
            "",
            "Apply recorded by harness. Implementation branch work is operator/fixer-owned.",
            "",
        ]) + "\n",
        encoding="utf-8",
    )
    return receipt_path
