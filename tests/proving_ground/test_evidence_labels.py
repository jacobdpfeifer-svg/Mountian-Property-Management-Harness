from __future__ import annotations

from src.proving_ground.evidence import SourceRecord, compute_evidence_label


def test_internal_only_blocks_publishable():
    label = compute_evidence_label([
        SourceRecord("nrcs", "publishable"),
        SourceRecord("sample", "internal_only"),
    ])
    assert label == "internal_only"


def test_all_publishable():
    label = compute_evidence_label([
        SourceRecord("nrcs", "publishable"),
        SourceRecord("noaa", "publishable"),
    ])
    assert label == "publishable"
