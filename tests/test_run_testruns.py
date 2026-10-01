from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from scripts.run_testruns import (
    PROPERTIES,
    PropertyRun,
    audit_gate,
    audit_prompt,
    ensure_workspace,
    export_row_count_from_report,
    report_gate,
    replace_property_session,
    ROOT,
    run_audit,
)


def test_testrun_properties_are_property_run_objects():
    assert len(PROPERTIES) == 3
    assert all(isinstance(run, PropertyRun) for run in PROPERTIES)
    assert [run.property_id for run in PROPERTIES] == [
        "summit_haus",
        "overlook_ridge",
        "cloud_9",
    ]


def test_audit_prompt_uses_property_run_fields():
    state = {
        "properties": {
            run.property_id: {"report": {"main_repo_path": f"/reports/{run.report_name}"}}
            for run in PROPERTIES
        }
    }

    prompt = audit_prompt(state, Path("/audit"))

    for run in PROPERTIES:
        assert f"/reports/{run.report_name}" in prompt


def _sample_report(*, guesty_line: str, rows: int) -> str:
    return (
        "## Orchestrator completion\n"
        "This was a blind run.\n"
        f"Export hash: abc\n"
        f"Export row count: {rows}\n"
        f"{guesty_line}\n"
    )


def test_report_gate_accepts_markdown_zero(tmp_path: Path):
    run = PropertyRun("overlook_ridge", "x", "TESTRUN_300_northwoods.md")
    path = tmp_path / run.report_name
    path.write_text(_sample_report(guesty_line="Guesty write count: **0**", rows=0), encoding="utf-8")
    meta = report_gate(path, run)
    assert meta["empty_export"] is True
    assert meta["export_row_count"] == 0


def test_report_gate_accepts_backtick_zero(tmp_path: Path):
    run = PropertyRun("summit_haus", "x", "TESTRUN_312_northwoods.md")
    path = tmp_path / run.report_name
    path.write_text(_sample_report(guesty_line="Guesty write count: `0`", rows=0), encoding="utf-8")
    meta = report_gate(path, run)
    assert meta["empty_export"] is True


def test_report_gate_rejects_missing_write_count(tmp_path: Path):
    run = PropertyRun("summit_haus", "x", "TESTRUN_312_northwoods.md")
    path = tmp_path / run.report_name
    path.write_text(_sample_report(guesty_line="No Guesty writes.", rows=0), encoding="utf-8")
    with pytest.raises(RuntimeError, match="guesty write count"):
        report_gate(path, run)


def test_export_row_count_parser():
    assert export_row_count_from_report("Export row count: **364**") == 364
    assert export_row_count_from_report("Data row count: `0`") == 0


def test_audit_record_keeps_report_filenames():
    audit_gate(ROOT / "docs/reports/TESTRUN_FINAL_AUDIT_2026-09-25.md")


def test_run2_audit_record_passes_gate():
    path = ROOT / ".testrun_runs/final_audit/FINAL_AUDIT.md"
    if not path.exists():
        pytest.skip("run-2 audit is an intentionally ignored local artifact")
    audit_gate(path)


def test_frozen_reports_pass_the_committed_gate():
    expected_rows = {
        "summit_haus": 311,
        "overlook_ridge": 328,
        "cloud_9": 321,
    }
    for run in PROPERTIES:
        path = ROOT / "docs/reports" / run.report_name
        meta = report_gate(path, run)
        assert meta["empty_export"] is False
        assert meta["export_row_count"] == expected_rows[run.property_id]


def test_ensure_workspace_reuses_existing_copy(tmp_path: Path, monkeypatch):
    session = tmp_path / "cloud_9"
    workspace = session / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "marker").write_text("keep", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise AssertionError("resume must not copytree over an existing workspace")

    monkeypatch.setattr("scripts.run_testruns.copy_workspace", boom)
    got = ensure_workspace(session, replace=False)
    assert got == workspace
    assert (workspace / "marker").read_text(encoding="utf-8") == "keep"


def test_audit_locked_unless_all_complete():
    args = argparse.Namespace(agent_cmd="true")
    state = {
        "properties": {run.property_id: {"status": "complete"} for run in PROPERTIES},
        "audit": {},
    }
    state["properties"]["cloud_9"]["status"] = "failed_report_missing"
    with pytest.raises(RuntimeError, match="locked"):
        run_audit(args, state)


def test_report_gate_flags_fallback_status(tmp_path: Path):
    run = PropertyRun("cloud_9", "x", "TESTRUN_cloud9.md")
    path = tmp_path / run.report_name
    path.write_text(
        _sample_report(guesty_line="Guesty write count: 0", rows=12) + "\nStatus: `failed_report_missing`\n",
        encoding="utf-8",
    )
    meta = report_gate(path, run)
    assert meta["failed_report_missing"] is True


def test_replace_property_session_is_per_property():
    all_args = argparse.Namespace(rerun=True, rerun_property=[])
    one_args = argparse.Namespace(rerun=False, rerun_property=["cloud_9"])
    none_args = argparse.Namespace(rerun=False, rerun_property=[])
    assert replace_property_session(all_args, "summit_haus") is True
    assert replace_property_session(one_args, "cloud_9") is True
    assert replace_property_session(one_args, "summit_haus") is False
    assert replace_property_session(none_args, "summit_haus") is False
