from __future__ import annotations

import pytest

from src.proving_ground import apply as apply_mod
from src.proving_ground.apply import apply_fix


def _redirect(monkeypatch, tmp_path):
    """Point the apply gate at a disposable docs tree so tests never depend on the
    live docs/proving_ground/APPROVAL_QUEUE.md (whose decisions legitimately change)."""
    queue = tmp_path / "APPROVAL_QUEUE.md"
    proposals = tmp_path / "proposals"
    receipts = tmp_path / "receipts"
    proposals.mkdir()
    monkeypatch.setattr(apply_mod, "ROOT", tmp_path)
    monkeypatch.setattr(apply_mod, "QUEUE", queue)
    monkeypatch.setattr(apply_mod, "PROPOSALS", proposals)
    monkeypatch.setattr(apply_mod, "RECEIPTS", receipts)
    return queue, proposals, receipts


def test_apply_refuses_when_decision_pending(tmp_path, monkeypatch):
    queue, _proposals, _receipts = _redirect(monkeypatch, tmp_path)
    queue.write_text(
        "## Fix Card FIX-P0-001\n\nOperator decision: pending\nDecision date:\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError):
        apply_fix("FIX-P0-001")


def test_apply_refuses_for_unknown_card(tmp_path, monkeypatch):
    queue, _proposals, _receipts = _redirect(monkeypatch, tmp_path)
    queue.write_text("## Fix Card FIX-P0-001\n\nOperator decision: Approve\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        apply_fix("FIX-DOES-NOT-EXIST")


def test_apply_writes_receipt_when_approved(tmp_path, monkeypatch):
    queue, proposals, receipts = _redirect(monkeypatch, tmp_path)
    queue.write_text(
        "## Fix Card FIX-P0-001\n\n"
        "Operator decision: Approve\nDecision date: 2026-09-25\nOperator notes: ok\n",
        encoding="utf-8",
    )
    (proposals / "FIX-P0-001.md").write_text("# proposal", encoding="utf-8")

    receipt = apply_fix("FIX-P0-001")

    assert receipt == receipts / "FIX-P0-001-receipt.md"
    body = receipt.read_text(encoding="utf-8")
    assert "Decision: **approve** on 2026-09-25" in body
