"""Owner-facing reason rendering — presentation only, ranking unchanged."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from src.compose import generate_recommendations
from src.config import load_policy
from src.db import connect, init_db
from src.explain import Reason, select_top_reasons
from src.explain.present import (
    COMPOSE_REASON_CODES,
    OWNER_TEMPLATES,
    MissingOwnerTemplateError,
    format_owner_recommendation,
    owner_price_range,
    owner_text_has_jargon,
    render_owner_reason,
    serialize_owner_reason,
)
from src.ingest import CsvIngestAdapter

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
COMPOSE_SRC = ROOT / "src" / "compose" / "__init__.py"


def _adapter() -> CsvIngestAdapter:
    return CsvIngestAdapter(
        properties_csv=SAMPLE / "properties.csv",
        inventory_csv=SAMPLE / "nightly_inventory.csv",
        comps_csv=SAMPLE / "comps.csv",
        demand_csv=SAMPLE / "demand_signals.csv",
        inquiries_csv=SAMPLE / "booking_inquiries.csv",
    )


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "test.db"
    init_db(path)
    with connect(path) as conn:
        _adapter().load_all(conn)
    return path


def _compose_emitted_codes() -> set[str]:
    text = COMPOSE_SRC.read_text(encoding="utf-8")
    codes = set(re.findall(r'Reason\(\s*"([a-z_]+)"', text))
    codes.update(
        re.findall(
            r'"(?:peak_underprice|orphan_gap|shoulder_over_discount|access_cliff)"\s*:\s*"([a-z_]+)"',
            text,
        )
    )
    return codes


def test_every_compose_reason_code_has_an_owner_template():
    emitted = _compose_emitted_codes()
    assert emitted == COMPOSE_REASON_CODES, (
        f"Update COMPOSE_REASON_CODES; compose emits {sorted(emitted)} "
        f"but the declared set is {sorted(COMPOSE_REASON_CODES)}"
    )
    missing = COMPOSE_REASON_CODES - set(OWNER_TEMPLATES)
    assert not missing, (
        f"New compose reason code(s) {sorted(missing)} have no owner template. "
        "Add a template in src/explain/present.py — do not fall back to internals."
    )


def test_missing_template_fails_loudly():
    with pytest.raises(MissingOwnerTemplateError, match="No owner-facing template"):
        render_owner_reason({"code": "brand_new_undocumented_signal", "facts": {}})


def _sample_reason(code: str) -> Reason:
    facts = {
        "optimum": 720,
        "book_prob": 0.41,
        "ceiling": 980,
        "season": "peak_ski",
        "thin": True,
        "kind": "thin_pool",
        "anchor": 650,
        "listed": 600,
        "comp_price": 810,
        "comp_observed": 3,
        "reduction_pct": 0.08,
        "event": "Sundance week",
        "pacing_ratio": 0.7,
        "gap_size": 2,
        "standing_min_stay": 4,
        "shoulder_floor": 480,
        "lead_days": 3,
        "nights": 2,
        "source": "gap_override",
        "gap_override": True,
        "conversion_rate": 0.08,
        "action": "clamped_increase",
    }
    return Reason(
        code,  # type: ignore[arg-type]
        f"INTERNAL beta=0.32 SQI bucket n={12}",
        contribution=40.0,
        facts=facts,
    )


def test_templates_for_compose_codes_contain_no_jargon():
    for code in sorted(COMPOSE_REASON_CODES):
        text = render_owner_reason(_sample_reason(code))
        assert text.strip(), f"{code} rendered empty"
        assert not owner_text_has_jargon(text), f"{code} leaked jargon: {text}"


def test_serialized_default_message_is_owner_facing():
    reason = _sample_reason("revpan_optimum")
    payload = serialize_owner_reason(reason)
    assert not owner_text_has_jargon(payload["message"])
    assert "beta" in payload["technical_message"]
    assert "SQI" in payload["technical_message"]
    assert "n=" in payload["technical_message"]


def test_recommendations_default_surface_has_range_sources_and_no_jargon(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        recs, _ = generate_recommendations(
            conn, date(2026, 12, 1), date(2026, 12, 14),
            property_ids=["aspen_glow"], policy=policy, persist=False,
        )
    assert recs
    for rec in recs:
        assert rec.range_low is not None and rec.range_high is not None
        assert rec.range_low <= rec.recommended_price <= rec.range_high
        assert rec.evidence_count >= 1
        block = format_owner_recommendation(rec)
        assert "–" in block or "-" in block
        assert "SOURCE" in block
        assert not owner_text_has_jargon(block)
        for r in rec.reasons:
            assert r["code"] in OWNER_TEMPLATES
            assert not owner_text_has_jargon(r["message"])
            assert "technical_message" in r


def test_price_range_narrows_as_confidence_rises():
    wide = owner_price_range(
        recommended=700, floor=400, ceiling=1200, confidence=0.2, round_to=5,
    )
    tight = owner_price_range(
        recommended=700, floor=400, ceiling=1200, confidence=0.95, round_to=5,
    )
    assert wide[0] <= 700 <= wide[1]
    assert tight[0] <= 700 <= tight[1]
    assert (tight[1] - tight[0]) < (wide[1] - wide[0])
    clipped = owner_price_range(
        recommended=700, floor=690, ceiling=710, confidence=0.0, round_to=5,
    )
    assert clipped[0] >= 690
    assert clipped[1] <= 710


def test_dollar_ranking_is_unchanged_by_facts():
    reasons = [
        Reason("base_compose", "boilerplate", contribution=0.0, facts={"ceiling": 1}),
        Reason("season", "small", contribution=5.0, facts={"season": "shoulder"}),
        Reason("ceiling_gap", "the real driver", contribution=-120.0, facts={"listed": 1}),
    ]
    top = select_top_reasons(reasons, max_n=2)
    assert top[0].code == "ceiling_gap"
    assert top[1].code == "season"
