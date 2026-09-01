"""Intrawest feed parser tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.signals.extractors.intrawest import parse_intrawest_payload, summarize_lifts

FIXTURE = Path(__file__).parent / "fixtures" / "signals" / "intrawest_winter_park_lifts.json"


def test_summarize_winter_fixture():
    lifts = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = summarize_lifts(lifts)
    assert summary["lift_total"] == 5
    assert summary["lifts_open"] == pytest.approx(2.0)  # Gondola + Super Gauge
    assert summary["lifts_on_hold"] == pytest.approx(1.0)  # Panoramic
    assert summary["trails_open"] == pytest.approx(4.0)
    assert summary["terrain_open_pct"] == pytest.approx(50.0)
    assert summary["resort_open"] == pytest.approx(1.0)
    assert summary["trails_groomed_pct"] == pytest.approx(50.0)  # 2 of 4 open groomed


def test_parse_intrawest_payload():
    lifts = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data = parse_intrawest_payload(lifts, source_url="https://example.com")
    assert data["source_url"] == "https://example.com"
    assert "lifts" in data
