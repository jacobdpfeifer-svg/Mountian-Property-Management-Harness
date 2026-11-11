"""Conservative scenario-based profitability model, isolated from owner data."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LABEL = "ASSUMPTION-BASED"
REQUIRED_SCENARIOS = ("downside", "base", "upside")
REQUIRED_INPUTS = frozenset({"occupancy", "adr_usd", "price_elasticity", "channel_fee_pct", "management_fee_pct", "cleaning_turn_per_stay_usd", "maintenance_per_booked_night_usd", "annual_system_cost_usd", "sellable_nights", "incremental_owner_net_per_available_night_usd", "average_length_of_stay_nights"})


class ModelError(ValueError):
    """The synthetic model document is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    inputs: dict[str, float]
    annual_booked_nights: float
    annual_stays: float
    modeled_gross_lodging: float
    modeled_owner_net_before_system: float
    annual_incremental_owner_net: float
    annual_net_after_system_cost: float
    break_even_incremental_owner_net_per_available_night: float
    clears_downside_hurdle: bool

    def as_dict(self) -> dict[str, Any]:
        return {"label": LABEL, "scenario": self.name, "inputs": self.inputs,
                "annual_booked_nights": self.annual_booked_nights, "annual_stays": self.annual_stays,
                "modeled_gross_lodging": self.modeled_gross_lodging,
                "modeled_owner_net_before_system": self.modeled_owner_net_before_system,
                "annual_incremental_owner_net": self.annual_incremental_owner_net,
                "annual_net_after_system_cost": self.annual_net_after_system_cost,
                "break_even_incremental_owner_net_per_available_night": self.break_even_incremental_owner_net_per_available_night,
                "clears_hurdle": self.clears_downside_hurdle}


def _number(value: Any, key: str, scenario: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelError(f"{scenario}.{key} must be a number")
    return float(value)


def load_model(path: Path) -> dict[str, Any]:
    """Read a synthetic-only economic model and validate its strict contract."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ModelError(f"cannot read model: {path}") from exc
    if not isinstance(raw, dict) or raw.get("data_classification") != LABEL:
        raise ModelError(f"model must declare data_classification: {LABEL}")
    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, dict) or set(scenarios) != set(REQUIRED_SCENARIOS):
        raise ModelError("model must contain exactly downside, base, and upside scenarios")
    for name in REQUIRED_SCENARIOS:
        spec = scenarios[name]
        inputs = spec.get("inputs", {}) if isinstance(spec, dict) else {}
        if not isinstance(spec, dict) or set(inputs) != REQUIRED_INPUTS:
            raise ModelError(f"{name}.inputs must have every documented field")
        for key, value in inputs.items():
            val = _number(value, key, name)
            if key.endswith("_pct") or key == "occupancy":
                if not 0 <= val <= 1:
                    raise ModelError(f"{name}.{key} must be in [0, 1]")
            elif key == "price_elasticity":
                if val >= 0:
                    raise ModelError(f"{name}.price_elasticity must be negative")
            elif key != "incremental_owner_net_per_available_night_usd" and val <= 0:
                raise ModelError(f"{name}.{key} must be positive")
    return raw


def evaluate_scenario(name: str, inputs: dict[str, Any]) -> ScenarioResult:
    """Compute transparent owner economics and the exact incremental-payback equation."""
    i = {key: _number(value, key, name) for key, value in inputs.items()}
    booked = i["sellable_nights"] * i["occupancy"]
    stays = booked / i["average_length_of_stay_nights"]
    gross = booked * i["adr_usd"]
    retained = gross * (1 - i["channel_fee_pct"] - i["management_fee_pct"])
    owner_net = retained - stays * i["cleaning_turn_per_stay_usd"] - booked * i["maintenance_per_booked_night_usd"]
    incremental = i["sellable_nights"] * i["incremental_owner_net_per_available_night_usd"]
    net_after_system = incremental - i["annual_system_cost_usd"]
    hurdle = i["annual_system_cost_usd"] / i["sellable_nights"]
    return ScenarioResult(name, i, round(booked, 2), round(stays, 2), round(gross, 2), round(owner_net, 2), round(incremental, 2), round(net_after_system, 2), round(hurdle, 2), net_after_system > 0)


def evaluate_model(model: dict[str, Any]) -> dict[str, Any]:
    scenarios = [evaluate_scenario(name, model["scenarios"][name]["inputs"]) for name in REQUIRED_SCENARIOS]
    downside = scenarios[0]
    return {"label": LABEL,
            "decision": "CLEAR_DOWNSIDE_HURDLE" if downside.clears_downside_hurdle else "DO_NOT_SCALE_WITHOUT_NARROWER_SCOPE",
            "decision_basis": "Downside annual incremental owner net after system cost must be positive; this is not realized profit.",
            "scenario_results": [r.as_dict() for r in scenarios], "limitations": model.get("limitations", []),
            "source_register": model.get("source_register", [])}


def render_markdown(result: dict[str, Any], *, model_path: Path) -> str:
    rows = result["scenario_results"]
    out = ["# Profitability under uncertainty", "", f"**Classification:** {LABEL}. This is a synthetic, assumption-based investment model, not settled owner net, realized profit, a valuation, or authority to change rates.", "", f"**Model:** `{model_path}`  ", f"**Decision:** `{result['decision']}` — {result['decision_basis']}", "", "## Scenario results", "", "| Scenario | Occupancy | ADR | Gross lodging | Modeled owner net before system | Incremental owner net / available night | Annual incremental owner net | Annual system cost | Net after system cost | Break-even / available night |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        i = r["inputs"]
        out.append(f"| {r['scenario']} | {i['occupancy']:.0%} | ${i['adr_usd']:,.0f} | ${r['modeled_gross_lodging']:,.0f} | ${r['modeled_owner_net_before_system']:,.0f} | ${i['incremental_owner_net_per_available_night_usd']:,.2f} | ${r['annual_incremental_owner_net']:,.0f} | ${i['annual_system_cost_usd']:,.0f} | ${r['annual_net_after_system_cost']:,.0f} | ${r['break_even_incremental_owner_net_per_available_night']:,.2f} |")
    out += ["", "## Limits", ""] + [f"- {x}" for x in result["limitations"]] + ["", "## Sources", ""]
    out += [f"- **{s['id']} ({s['classification']}):** {s['claim']} — {s['url']}" for s in result["source_register"]]
    return "\n".join(out) + "\n"
