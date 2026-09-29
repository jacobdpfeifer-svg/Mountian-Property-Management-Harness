"""Download and freeze L2 public-domain vintages (NRCS SNOTEL + NOAA CPC ENSO)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.signals.collectors.enso import ONI_URL
from src.signals.collectors.snotel import AWDB_DATA, fetch_awdb, peak_swe_by_season, parse_awdb_payload

ROOT = Path(__file__).resolve().parents[2]
VINTAGE_ROOT = ROOT / "data" / "proving_ground" / "vintages"
BERTHOUD = "335:CO:SNTL"


@dataclass(frozen=True)
class FrozenFile:
    path: str
    url: str
    retrieved_at: str
    published_at: str
    sha256: str
    license_class: str


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_median_snotel_season(series: list[tuple[date, float]]) -> str:
    peaks = peak_swe_by_season(series)
    if not peaks:
        raise ValueError("no SNOTEL peaks in vintage payload")
    ordered = sorted(peaks.items())
    return ordered[len(ordered) // 2][0]


def build_vintages(*, ski_season_begin: date | None = None, ski_season_end: date | None = None) -> dict[str, Any]:
    """Fetch AWDB + ONI and write manifest under data/proving_ground/vintages/."""
    import requests

    VINTAGE_ROOT.mkdir(parents=True, exist_ok=True)
    snotel_dir = VINTAGE_ROOT / "snotel"
    enso_dir = VINTAGE_ROOT / "enso"
    snotel_dir.mkdir(parents=True, exist_ok=True)
    enso_dir.mkdir(parents=True, exist_ok=True)

    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    begin = ski_season_begin or date(2018, 10, 1)
    end = ski_season_end or date(2025, 4, 30)

    payload = fetch_awdb([BERTHOUD], begin, end)
    snotel_path = snotel_dir / f"berthoud_wteq_{begin.year}_{end.year}.json"
    snotel_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    swe = parse_awdb_payload(payload, "WTEQ")
    median_season = select_median_snotel_season([(d, v) for d, v in swe if v is not None])

    r = requests.get(ONI_URL, timeout=60)
    r.raise_for_status()
    oni_path = enso_dir / "oni_ascii.txt"
    oni_path.write_text(r.text, encoding="utf-8")

    files = [
        FrozenFile(
            path=str(snotel_path.relative_to(ROOT)),
            url=AWDB_DATA,
            retrieved_at=retrieved,
            published_at=end.isoformat(),
            sha256=_sha256_file(snotel_path),
            license_class="publishable",
        ),
        FrozenFile(
            path=str(oni_path.relative_to(ROOT)),
            url=ONI_URL,
            retrieved_at=retrieved,
            published_at=date.today().isoformat(),
            sha256=_sha256_file(oni_path),
            license_class="publishable",
        ),
    ]
    manifest = {
        "median_snotel_season": median_season,
        "files": [asdict(f) for f in files],
    }
    manifest_path = VINTAGE_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_vintage_manifest() -> dict[str, Any] | None:
    path = VINTAGE_ROOT / "manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
