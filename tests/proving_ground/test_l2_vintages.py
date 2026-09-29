from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.proving_ground.vintages import ROOT, load_vintage_manifest


def test_l2_vintage_manifest_rehashes_when_present():
    manifest = load_vintage_manifest()
    if manifest is None:
        return  # run wp-price proving-ground build-vintages to populate
    root = ROOT
    for f in manifest.get("files", []):
        path = root / f["path"]
        assert path.exists()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == f["sha256"]


def test_median_season_field_when_manifest_exists():
    manifest = load_vintage_manifest()
    if manifest is None:
        return
    assert "median_snotel_season" in manifest
