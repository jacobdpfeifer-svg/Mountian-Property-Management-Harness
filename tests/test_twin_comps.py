from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPS = ROOT / "data" / "scrape" / "comps.csv"

OUT_OF_MARKET = (
    "breckenridge", "breck", "vail", "keystone", "silverthorne",
    "beaver creek", "avon", "frisco", "eagle county",
)


def test_twin_comps_are_winter_park_fraser_peers():
    with COMPS.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 14
    blob = " ".join(
        f"{r['name']} {r['notes']} {r['source_url']}" for r in rows
    ).lower()
    for token in OUT_OF_MARKET:
        assert token not in blob, f"out-of-market token {token!r} still in twin comps"
    ids = {r["airbnb_room_id"] for r in rows}
    assert "12345678901" not in ids
    assert all(r["platform"] == "airbnb" for r in rows)
    for row in rows:
        props = set(row["for_properties"].split("|"))
        assert props <= {"summit_haus", "overlook_ridge"}
