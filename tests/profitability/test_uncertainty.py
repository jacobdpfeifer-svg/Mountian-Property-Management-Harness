"""The synthetic profitability model must stay isolated and conservative."""
from pathlib import Path

import pytest

from src.profitability.uncertainty import LABEL, ModelError, evaluate_model, load_model, render_markdown

ROOT = Path(__file__).parents[2]
MODEL = ROOT / "config" / "synthetic" / "profitability_under_uncertainty.yaml"


def test_model_is_assumption_based_and_downside_fails_to_clear_hurdle():
    result = evaluate_model(load_model(MODEL))
    assert result["label"] == LABEL
    assert result["decision"] == "DO_NOT_SCALE_WITHOUT_NARROWER_SCOPE"
    downside = result["scenario_results"][0]
    assert downside["annual_net_after_system_cost"] == -64500.0
    assert downside["break_even_incremental_owner_net_per_available_night"] == 66.67


def test_render_cannot_claim_realized_profit():
    text = render_markdown(evaluate_model(load_model(MODEL)), model_path=MODEL)
    assert "ASSUMPTION-BASED" in text
    assert "not settled owner net" in text.lower()
    assert "not settled owner net, realized profit" in text.lower()


def test_model_rejects_unlabelled_inputs(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("data_classification: SETTLED-ACTUAL\n", encoding="utf-8")
    with pytest.raises(ModelError, match="ASSUMPTION-BASED"):
        load_model(path)


def test_cli_returns_conservative_decision_and_writes_no_database(tmp_path, capsys):
    from src.cli.main import main

    report = tmp_path / "report.md"
    with pytest.raises(SystemExit) as exc:
        main(["profitability-uncertainty", "--out", str(report)])
    assert exc.value.code == 3
    assert report.is_file()
    assert not list(tmp_path.glob("*.db"))
    output = capsys.readouterr().out
    assert "Guesty writes: 0" in output
    assert "Data-spine writes: 0" in output
