from __future__ import annotations

from pathlib import Path

from scripts.run_testruns import PROPERTIES, PropertyRun, audit_prompt


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
